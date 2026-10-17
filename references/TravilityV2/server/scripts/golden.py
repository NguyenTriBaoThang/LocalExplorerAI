"""Golden set (một phần #6): đo agent đơn và đa agent trên cùng bộ prompt (spec scale §7).

Chạy: uv run python -m scripts.golden --mode both --rpm 14
Cần database dev đã import Place và LLM_* / EMBED_* thật trong .env. Đa agent luôn chạy bằng thread
trong tiến trình (không cần cụm). Muốn đo thời gian thật thì trỏ thẳng provider, không qua cache của llm-gateway.
"""
import argparse
import datetime as dt
import threading
import time
from collections import deque
from functools import partial
from types import SimpleNamespace

from app import agent, forecast, llm, multi, trips
from app.config import settings
from app.db import connect
from app.domain import TripAnswers
from app.places_client import list_destinations

_now, _sleep = time.monotonic, time.sleep  # test thay bằng đồng hồ giả
_DATE = (dt.date.today() + dt.timedelta(days=10)).isoformat()
PROMPTS = [
    "Đà Lạt 1 ngày 1 triệu cho 2 người, đi Grab",
    "Đà Lạt 2 ngày 3 triệu 2 người, thích cafe và chụp ảnh, thuê xe máy",
    "Đi Đà Lạt 3 ngày, 4 người, ngân sách 8 triệu, đi nhẹ nhàng thong thả, có ô tô riêng",
    "Đà Lạt 3 ngày 5 triệu 2 người, muốn khám phá hết, đi thật nhiều, thuê xe máy",
    "Đà Lạt 2 ngày 1,5 triệu 2 người, tiết kiệm nhất có thể, thuê xe máy",
    "Gia đình 5 người có trẻ nhỏ đi Đà Lạt 2 ngày, 6 triệu, không leo núi, đi Grab",
    f"Đà Lạt 2 ngày từ {_DATE}, 2 người 4 triệu, bay tới lúc 10:00 và bay về lúc 17:00, đi Grab",
    "Cặp đôi đi Đà Lạt 4 ngày 10 triệu, thích thiên nhiên và ẩm thực địa phương, thuê xe máy",
]


class Throttle:
    """Giữ số lượt chat dưới hạn mức theo phút của provider (Gemini free: 15). rpm=0 = không hãm."""

    def __init__(self, rpm: int):
        self.rpm, self._starts, self._lock = rpm, deque(maxlen=rpm or 1), threading.Lock()

    def acquire(self) -> float:
        """Chờ nếu cửa sổ một phút đã đầy; trả số giây đã chờ."""
        if not self.rpm:
            return 0.0
        with self._lock:  # giữ khoá cả lúc ngủ: các chuyên gia ở thread khác cũng phải chờ
            wait = max(0.0, self._starts[0] + 61 - _now()) if len(self._starts) == self.rpm else 0.0
            if wait:
                _sleep(wait)
            self._starts.append(_now())
            return wait

    def drain(self) -> None:
        """Trước mỗi prompt: chờ cửa sổ trống, để prompt không bị hãm giữa chừng (không tính vào thời gian đo)."""
        if self.rpm and self._starts:
            _sleep(max(0.0, self._starts[-1] + 61 - _now()))
            self._starts.clear()


class Counting:
    """Bọc client OpenAI: đếm lượt chat và hãm theo phút (các chuyên gia gọi từ nhiều thread)."""

    def __init__(self, inner, throttle: Throttle):
        self.n, self.waited, self._inner, self._throttle = 0, 0.0, inner, throttle
        self._lock = threading.Lock()
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def with_options(self, **options):
        self._inner = self._inner.with_options(**options)
        return self

    def _create(self, **kwargs):
        waited = self._throttle.acquire()
        with self._lock:
            self.n += 1
            self.waited += waited
        return self._inner.chat.completions.create(**kwargs)


def run_one(conn, dests: dict, prompt: str, mode: str, throttle: Throttle) -> dict:
    client = Counting(llm.chat_client(), throttle)
    row = {"valid": False, "conflicts": 0, "fallback": False, "error": ""}
    t0 = time.perf_counter()
    try:
        today = trips._today()
        trip = agent.apply_answers(
            agent.parse_trip(client, settings.llm_model, prompt, {s: d["name"] for s, d in dests.items()}, today),
            TripAnswers())
        d = dests[trip.destination]
        rain = forecast.get_rain_chance(d["lat"], d["lon"], trip.start_date, trip.days, today=today)
        planner = partial(multi.plan, local=True) if mode == "multi" else agent.plan
        for ev in planner(conn, client, settings.llm_model, trip, llm.embed, rain, trips.hub_for(d, trip), [prompt]):
            if ev["type"] == "thinking" and ev["text"] == multi.FALLBACK_TEXT:
                row["fallback"] = True
            elif ev["type"] == "itinerary":
                row.update(valid=True, conflicts=len(ev["itinerary"]["conflicts"]))
            elif ev["type"] == "error":
                row["error"] = ev["message"]
    except Exception as e:  # một prompt hỏng không dừng cả lượt đo
        row["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return {**row, "seconds": round(time.perf_counter() - t0 - client.waited, 1), "calls": client.n,
            "waited": round(client.waited, 1)}


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["valid"]]

    def mean(xs):
        return round(sum(xs) / len(xs), 1) if xs else 0.0

    return {"n": len(rows), "valid_pct": round(100 * len(ok) / len(rows)) if rows else 0,
            "conflicts": mean([r["conflicts"] for r in ok]), "seconds": mean([r["seconds"] for r in rows]),
            "calls": mean([r["calls"] for r in rows]), "fallbacks": sum(r["fallback"] for r in rows)}


def table(by_mode: dict[str, dict]) -> str:
    lines = ["| Chế độ | Prompt | Itinerary hợp lệ | Conflict TB | Giây TB | Lượt LLM TB | Về dự phòng |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {m} | {s['n']} | {s['valid_pct']}% | {s['conflicts']} | {s['seconds']} | {s['calls']} | "
              f"{s['fallbacks']} |" for m, s in by_mode.items()]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["single", "multi", "both"], default="both")
    ap.add_argument("--rpm", type=int, default=0,
                    help="hãm số lượt chat mỗi phút (Gemini free: đặt 14); thời gian báo đã trừ phần chờ")
    args = ap.parse_args()
    modes = ["single", "multi"] if args.mode == "both" else [args.mode]
    throttle, by_mode = Throttle(args.rpm), {}
    with connect() as conn:
        dests = {d["slug"]: d for d in list_destinations(conn)}
        for mode in modes:
            rows = []
            for i, prompt in enumerate(PROMPTS, 1):
                throttle.drain()
                r = run_one(conn, dests, prompt, mode, throttle)
                rows.append(r)
                print(f"[{mode} {i}/{len(PROMPTS)}] hợp lệ={r['valid']} conflict={r['conflicts']} {r['seconds']}s "
                      f"lượt={r['calls']} dự phòng={r['fallback']} chờ hạn mức={r['waited']}s {r['error']}", flush=True)
            by_mode[mode] = summarize(rows)
    print(f"\nModel: {settings.llm_model}\n\n{table(by_mode)}")


if __name__ == "__main__":
    main()
