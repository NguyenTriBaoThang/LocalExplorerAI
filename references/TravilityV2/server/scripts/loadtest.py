"""Load test cụm Travility (spec scale §12, S33): in bảng Markdown p50 / p95 / lượt mỗi giây.

Chạy từ máy ngoài, trỏ vào nginx; bật cụm với PLAN_RPM=0 để không bị giới hạn theo User.

  uv run python -m scripts.loadtest --label "2 api" --users 20 --rounds 25 --concurrency 50
  uv run python -m scripts.loadtest --label "cache bật (replay)" --users 20 --plans 20 --rounds 0
  uv run python -m scripts.loadtest --label "cache tắt" --users 2 --plans 2 --sequential --rounds 0

Đăng nhập không được đo: nginx giới hạn /auth/ ở 1 request mỗi giây theo IP, nên bước tạo User chạy trước và chậm.
Cần ít nhất một lượt --plans trước đó để User có Trip cho kịch bản "mở Trip".
"""
import argparse
import asyncio
import json
import math
import time

import httpx

PASSWORD = "travility-load"
MESSAGE = "Đà Lạt 1 ngày 1 triệu cho 2 người, đi Grab"  # đủ Travel Mode, không có ngày đi → không bị hỏi lại
HEADER = ("| Cấu hình | Kịch bản | Lượt | Lỗi | p50 (ms) | p95 (ms) | Lượt/giây |\n"
          "|---|---|---|---|---|---|---|")


def percentile(xs: list[float], p: float) -> float:
    """Phân vị theo hạng gần nhất; danh sách rỗng → 0."""
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[max(0, math.ceil(p * len(s)) - 1)]


def summarize(samples: list[float], errors: int, wall: float) -> dict:
    """samples: giây của từng lượt thành công; wall: giây từ lúc bắt đầu tới lúc xong cả đợt."""
    return {"n": len(samples) + errors, "errors": errors, "p50_ms": round(percentile(samples, 0.5) * 1000),
            "p95_ms": round(percentile(samples, 0.95) * 1000), "rps": round(len(samples) / wall, 1) if wall else 0.0}


def row(label: str, scenario: str, s: dict) -> str:
    return f"| {label} | {scenario} | {s['n']} | {s['errors']} | {s['p50_ms']} | {s['p95_ms']} | {s['rps']} |"


async def token_for(http: httpx.AsyncClient, i: int) -> str:
    """Đăng ký User loadtest{i} (đã có hoặc đang chỉ đọc thì đăng nhập); nginx trả 429 thì chờ rồi thử lại."""
    body = {"email": f"loadtest{i}@travility.vn", "password": PASSWORD}
    for path in ("/auth/register", "/auth/login"):
        while (r := await http.post(path, json=body)).status_code == 429:
            await asyncio.sleep(1.1)
        if r.status_code in (200, 201):
            return r.json()["token"]
    raise SystemExit(f"Không tạo được User loadtest{i}: {r.status_code} {r.text[:200]}")


async def get_ok(http: httpx.AsyncClient, path: str, h: dict) -> bool:
    return (await http.get(path, headers=h)).status_code == 200


async def plan(http: httpx.AsyncClient, h: dict, message: str) -> bool:
    """Một lượt lập lịch: đọc SSE tới hết; thành công khi event cuối là itinerary."""
    last = None
    async with http.stream("POST", "/trips", json={"message": message, "trip_id": None}, headers=h) as r:
        if r.status_code != 200:
            return False
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                last = json.loads(line[6:])["type"]
    return last == "itinerary"


async def _time(call, gate: asyncio.Semaphore) -> float | None:
    async with gate:  # đồng hồ chỉ chạy khi tới lượt: không tính thời gian xếp hàng ở phía script
        t0 = time.perf_counter()
        try:
            ok = await call
        except httpx.HTTPError:
            return None
        return time.perf_counter() - t0 if ok else None


async def measure(calls: list, concurrency: int = 50) -> dict:
    """Chạy mọi lượt, nhiều nhất `concurrency` lượt cùng lúc (1 = lần lượt), rồi tóm tắt."""
    gate = asyncio.Semaphore(concurrency)
    t0 = time.perf_counter()
    got = await asyncio.gather(*(_time(c, gate) for c in calls))
    done = [g for g in got if g is not None]
    return summarize(done, len(got) - len(done), time.perf_counter() - t0)


async def run(args) -> None:
    async with httpx.AsyncClient(base_url=args.base, timeout=180, limits=httpx.Limits(max_connections=None)) as http:
        heads = [{"Authorization": f"Bearer {await token_for(http, i)}"} for i in range(1, args.users + 1)]
        print(HEADER)
        if args.plans:
            calls = [plan(http, heads[i % len(heads)], args.message) for i in range(args.plans)]
            print(row(args.label, "lập lịch", await measure(calls, 1 if args.sequential else args.concurrency)),
                  flush=True)
        if args.rounds:
            calls = [get_ok(http, "/trips", h) for h in heads for _ in range(args.rounds)]
            print(row(args.label, "danh sách Trip", await measure(calls, args.concurrency)), flush=True)
            mine = [(h, (await http.get("/trips", headers=h)).json()) for h in heads]
            calls = [get_ok(http, f"/trips/{ts[0]['id']}", h) for h, ts in mine if ts for _ in range(args.rounds)]
            if calls:
                print(row(args.label, "mở Trip", await measure(calls, args.concurrency)), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Load test cụm Travility")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--label", required=True, help="tên cấu hình đang đo, in ở cột đầu")
    ap.add_argument("--users", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=10, help="số lượt đọc mỗi User cho mỗi kịch bản đọc; 0 = bỏ")
    ap.add_argument("--plans", type=int, default=0, help="số lượt lập lịch; 0 = bỏ")
    ap.add_argument("--concurrency", type=int, default=50,
                    help="số lượt chạy cùng lúc; nginx mặc định chỉ giữ được khoảng 250 kết nối proxy")
    ap.add_argument("--sequential", action="store_true", help="lập lịch lần lượt (đo cache tắt với provider thật)")
    ap.add_argument("--message", default=MESSAGE)
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
