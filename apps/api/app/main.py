import hashlib
import ipaddress
import json
import logging
import re
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import admin, ai, auth, bookings, catalog, chat, health, ml, ops, planner, provider, routing
from app.adapters.llm.provider import LLMNotConfigured, LLMProviderError
from app.core.config import settings
from app.core.request_context import current_request_id
from app.services.prompt_service import InvalidStructuredOutput
from app.services.rate_limit import check_rate_limit

app = FastAPI(title="Local Explorer AI API", version="0.1.0", description="Explore simulated local experiences and build feasible itineraries.", openapi_url="/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])
_request_logger = logging.getLogger("local_explorer.request")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if not settings.trusted_proxy_ips.strip():
        return peer
    try:
        trusted_networks = [ipaddress.ip_network(item.strip(), strict=False) for item in settings.trusted_proxy_ips.split(",") if item.strip()]
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not any(peer_ip in network for network in trusted_networks):
        return peer
    forwarded = request.headers.get("X-Forwarded-For", "")
    chain = [item.strip() for item in forwarded.split(",") if item.strip()] + [peer]
    for item in reversed(chain):
        try:
            address = ipaddress.ip_address(item)
        except ValueError:
            return peer
        if any(address in network for network in trusted_networks):
            continue
        return str(address)
    return peer


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request_id = supplied if _REQUEST_ID.fullmatch(supplied) else str(uuid4())
    request.state.request_id = request_id
    request_context_token = current_request_id.set(request_id)
    started = time.perf_counter()
    status_code = 500
    try:
        if settings.rate_limit_enabled and request.url.path not in {"/health", "/ready"} and not request.url.path.startswith(("/docs", "/openapi.json", "/redoc")):
            peer = _client_ip(request)
            client_key = hashlib.sha256(peer.encode("utf-8", errors="replace")).hexdigest()[:24]
            if request.url.path.startswith("/api/auth"):
                category, limit = "auth", settings.rate_limit_auth_per_minute
            elif request.url.path.startswith(("/api/chat", "/api/ai")):
                category, limit = "chat", settings.rate_limit_chat_per_minute
            else:
                category, limit = "general", settings.rate_limit_general_per_minute
            try:
                allowed, remaining = check_rate_limit(f"{settings.rate_limit_prefix}:{category}:{client_key}:{int(time.time()) // 60}", limit)
            except Exception:
                response = JSONResponse(status_code=503, content={"error": {"code": "RATE_LIMIT_STORE_UNAVAILABLE", "message": "Request protection is temporarily unavailable.", "request_id": request_id}})
                response.headers["Retry-After"] = "5"
                response.headers["X-Request-ID"] = request_id
                status_code = response.status_code
                return response
            if not allowed:
                response = JSONResponse(status_code=429, content={"error": {"code": "RATE_LIMITED", "message": "Too many requests; retry shortly.", "request_id": request_id}})
                response.headers["Retry-After"] = "60"
                response.headers["X-Request-ID"] = request_id
                status_code = response.status_code
                return response
            request.state.rate_limit_remaining = remaining
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        if settings.rate_limit_enabled and hasattr(request.state, "rate_limit_remaining"):
            response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
        return response
    finally:
        _request_logger.info(json.dumps({
            "request_id": request_id, "method": request.method, "path": request.url.path,
            "status": status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }, separators=(",", ":")))
        current_request_id.reset(request_context_token)


def error_response(request: Request, code: str, message: str, details: list | None = None, status_code: int = 400):
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "details": details or [], "request_id": getattr(request.state, "request_id", str(uuid4()))}})


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return error_response(request, detail.get("code", "HTTP_ERROR"), detail.get("message", str(exc.detail)), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]} for error in exc.errors()]
    return error_response(request, "VALIDATION_ERROR", "Request validation failed.", details, 422)


@app.exception_handler(LLMNotConfigured)
async def llm_not_configured_handler(request: Request, exc: LLMNotConfigured):
    return error_response(request, "LLM_NOT_CONFIGURED", str(exc), status_code=503)


@app.exception_handler(LLMProviderError)
async def llm_provider_error_handler(request: Request, exc: LLMProviderError):
    return error_response(request, "LLM_PROVIDER_ERROR", str(exc), status_code=502)


@app.exception_handler(InvalidStructuredOutput)
async def invalid_output_handler(request: Request, exc: InvalidStructuredOutput):
    return error_response(request, "INVALID_MODEL_OUTPUT", str(exc), status_code=502)


@app.get("/")
def root():
    return {"name": "Local Explorer AI API", "docs": "/docs", "data_mode": "simulated"}


app.include_router(health.router)
app.include_router(ops.router)
app.include_router(auth.router)
app.include_router(provider.router)
app.include_router(bookings.router)
app.include_router(admin.router)
app.include_router(catalog.router)
app.include_router(planner.router)
app.include_router(chat.router)
app.include_router(ai.router)
app.include_router(ml.router)
app.include_router(routing.router)
