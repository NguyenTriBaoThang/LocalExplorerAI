"""llm-gateway: proxy giao thức OpenAI đứng giữa các service và provider (spec scale §6).

Cache theo hash(request), giới hạn lượt gọi theo provider, chuyển sang provider phụ khi provider chính lỗi.
Chạy: uvicorn app.gateway:app
"""
import hashlib
import json
import time

import httpx
from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse, Response
from redis.exceptions import RedisError

from app import kv
from app.config import settings

CHAT, EMBED = "chat/completions", "embeddings"
MAX_WAIT_S = 30  # hết lượt của provider: chờ tối đa bấy nhiêu rồi mới trả 429
DOWN_S = 30  # provider chính lỗi FAILS_TO_SKIP lần liên tiếp → bỏ qua nó bấy nhiêu giây
FAILS_TO_SKIP = 3

app = FastAPI(title="Travility llm-gateway")
http = httpx.Client(timeout=60)  # test thay bằng MockTransport
_now, _sleep = time.time, time.sleep  # test thay bằng đồng hồ giả


def _redis(op: str, *args, default=None, **kw):
    """Gọi một lệnh Redis; không cấu hình hoặc lỗi → default (Redis lỗi thì bỏ qua, không chặn — spec §10)."""
    c = kv.client()
    if c is None:
        return default
    try:
        return getattr(c, op)(*args, **kw)
    except RedisError:
        return default


def _stat(name: str) -> None:
    _redis("incr", f"gw:stat:{name}")


def _synthetic(status: int, message: str) -> httpx.Response:
    """Lỗi do gateway tự sinh, cùng dạng thân lỗi của OpenAI để SDK phía gọi đọc được."""
    return httpx.Response(status, json={"error": {"message": message, "type": "gateway_error"}})


def _post(base: str, api_key: str, path: str, body: dict) -> httpx.Response:
    _stat("provider_call")
    try:
        return http.post(f"{base.rstrip('/')}/{path}", json=body, headers={"Authorization": f"Bearer {api_key}"})
    except httpx.HTTPError as e:
        return _synthetic(504, f"provider không phản hồi ({type(e).__name__})")


def _take_slot() -> bool:
    """Giữ một lượt gọi provider chính trong phút này. Hết lượt thì chờ sang phút sau, tối đa MAX_WAIT_S.

    ponytail: cửa sổ cố định theo phút, chỉ áp cho chat của provider chính. Embedding không giới hạn
    (cache không hết hạn nên gần như luôn trúng); cần thì thêm bộ đếm theo host của provider.
    """
    if not settings.llm_rpm:
        return True
    waited = 0.0
    while True:
        now = _now()
        key = f"gw:rl:{int(now // 60)}"
        n = _redis("incr", key, default=0)
        if n == 1:
            _redis("expire", key, 120)
        if n <= settings.llm_rpm:
            return True
        if waited >= MAX_WAIT_S:
            return False
        if not waited:
            _stat("wait")
        pause = min(60 - now % 60, MAX_WAIT_S - waited)
        _sleep(pause)
        waited += pause


def _failed(r: httpx.Response) -> bool:
    return r.status_code == 429 or r.status_code >= 500


def _call(path: str, body: dict) -> httpx.Response:
    if path == EMBED:
        # Không chuyển provider: hai provider cho hai không gian vector khác nhau, đổi là phải import lại Place (ADR-0003).
        return _post(settings.embed_base_url, settings.embed_api_key, path, body)
    r = _synthetic(503, "provider chính đang tạm nghỉ sau nhiều lỗi liên tiếp, thử lại sau ít giây")
    if not _redis("exists", "gw:down", default=0):
        if not _take_slot():
            return _synthetic(429, "llm-gateway: hết lượt gọi provider trong phút này, thử lại sau ít giây")
        r = _post(settings.llm_base_url, settings.llm_api_key, path, body)
        if not _failed(r):
            _redis("delete", "gw:fail")
            return r
        if _redis("incr", "gw:fail", default=0) >= FAILS_TO_SKIP:
            _redis("set", "gw:down", "1", ex=DOWN_S)
            _redis("delete", "gw:fail")
    if not settings.llm2_base_url:
        return r
    _stat("fallback")
    return _post(settings.llm2_base_url, settings.llm2_api_key, path, {**body, "model": settings.llm2_model})


def _cache_key(path: str, body: dict) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "gw:cache:" + hashlib.sha256(f"{path}\n{canon}".encode()).hexdigest()


def _handle(path: str, body: dict) -> Response:
    if body.get("stream"):
        return JSONResponse({"error": {"message": "llm-gateway không hỗ trợ stream"}}, status_code=400)
    mode, key = settings.gateway_cache, _cache_key(path, body)
    if mode != "off":
        hit = _redis("get", key)
        if hit is not None:
            _stat("hit")
            return Response(hit, media_type="application/json", headers={"X-Cache": "hit"})
        if mode == "replay":
            return JSONResponse({"error": {"message": "llm-gateway đang ở chế độ replay và chưa ghi phản hồi "
                                                      "cho request này"}}, status_code=503)
        _stat("miss")
    r = _call(path, body)
    if r.status_code == 200 and mode == "on":
        ttl = settings.gateway_chat_ttl if path == CHAT else 0  # embedding không hết hạn
        _redis("set", key, r.text, ex=ttl or None)
    return Response(r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"), headers={"X-Cache": "miss"})


@app.post("/v1/chat/completions")
def chat_completions(body: dict = Body(...)):
    return _handle(CHAT, body)


@app.post("/v1/embeddings")
def embeddings(body: dict = Body(...)):
    return _handle(EMBED, body)


@app.get("/health")
def health():
    return {"ok": True}
