import asyncio
import hashlib
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

<<<<<<< HEAD
from app.api.routes import admin, admin_bot, ai, analytics, auth, bookings, catalog, chat, health, mfa, ml, models_3d, ops, places_admin, planner, provider, rbac, reviews, routing, site_content, journey, recommendations, landmark_stories, meshy
=======
from app.api.routes import admin, admin_bot, ai, analytics, auth, bookings, catalog, chat, health, mfa, ml, models_3d, ops, places_admin, planner, provider, push_notifications, rbac, reviews, routing, site_content
>>>>>>> origin/main
from app.adapters.llm.provider import LLMNotConfigured, LLMProviderError
from app.api.auth_cookies import ACCESS_NAMES, REFRESH_NAMES
from app.api.guards import public
from app.auth import AuthError
from app.core.config import settings
from app.core.request_context import current_request_id
from app.core.client_ip import client_ip, request_scheme
from app.services.prompt_service import InvalidStructuredOutput
from app.services.auth_runtime import token_service
from app.services.rate_limit import check_rate_limit

@asynccontextmanager
async def lifespan(_: FastAPI):
    token_service()  # fail fast: the RS256 signing key is required in every environment
    from app.services.meshy import worker
    task = asyncio.create_task(worker()) if settings.app_env != "test" else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Local Explorer AI API", version="0.1.0", description="Explore verified local experiences and build feasible itineraries.", openapi_url="/openapi.json", lifespan=lifespan)
app.include_router(journey.router)
app.include_router(landmark_stories.router)
app.include_router(meshy.router)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])
_request_logger = logging.getLogger("local_explorer.request")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")


def _client_ip(request: Request) -> str:
    return client_ip(request, settings.trusted_proxy_ips)


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
            elif request.url.path.startswith(("/api/geocoding", "/api/ml")):
                category, limit = "costly", settings.rate_limit_costly_per_minute  # spends the Goong quota or CPU
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


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Baseline response hardening. Responses under /api/auth carry credentials or recovery codes: never cache them."""
    response = await call_next(request)
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/auth"):
        headers["Cache-Control"] = "no-store"
        headers["Pragma"] = "no-cache"
    if settings.app_env.lower() == "production" and (request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"):
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_allowed(request: Request, origin: str) -> bool:
    allowed = {item.rstrip("/") for item in settings.cors_origin_list} | {settings.web_app_url.rstrip("/")}
    if settings.portal_app_url:
        allowed.add(settings.portal_app_url.rstrip("/"))
    if origin.rstrip("/") in allowed:
        return True
    host = request.headers.get("host", "")
    parts = urlsplit(origin)
    # Same origin means same scheme as well as host: http://api.example.com is not https://api.example.com.
    return bool(host) and parts.netloc == host and parts.scheme == request_scheme(request, settings.trusted_proxy_ips)


@app.middleware("http")
async def origin_check_middleware(request: Request, call_next):
    """CSRF defence in depth for cookie-authenticated, state-changing requests (SameSite=Lax is the first layer)."""
    origin = request.headers.get("origin")
    if (request.method in _UNSAFE_METHODS and origin and "authorization" not in request.headers
            and any(request.cookies.get(name) for name in ACCESS_NAMES + REFRESH_NAMES)
            and not _origin_allowed(request, origin)):
        return error_response(request, "CSRF_ORIGIN_MISMATCH", "This request origin is not allowed.", status_code=403)
    return await call_next(request)


def error_response(request: Request, code: str, message: str, details: list | None = None, status_code: int = 400, headers: dict | None = None, diagnostics: dict | None = None):
    error = {"code": code, "message": message, "details": details or [], "request_id": getattr(request.state, "request_id", str(uuid4()))}
    if diagnostics:
        error["diagnostics"] = diagnostics
    return JSONResponse(status_code=status_code, headers=headers, content={"error": error})


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return error_response(request, exc.code, exc.message, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return error_response(
        request,
        detail.get("code", "HTTP_ERROR"),
        detail.get("message", str(exc.detail)),
        status_code=exc.status_code,
        diagnostics=detail.get("diagnostics"), headers=exc.headers,
    )


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


@app.get("/", dependencies=[Depends(public("API information"))])
def root():
    return {"name": "Local Explorer AI API", "docs": "/docs", "data_mode": "real" if settings.real_data_only else "mixed"}


app.include_router(health.router)
app.include_router(ops.router)
app.include_router(push_notifications.router)
app.include_router(auth.router)
app.include_router(mfa.router)
app.include_router(provider.router)
app.include_router(bookings.router)
app.include_router(admin.router)
app.include_router(rbac.router)
app.include_router(catalog.router)
app.include_router(planner.router)
app.include_router(recommendations.router)
app.include_router(chat.router)
app.include_router(ai.router)
app.include_router(ml.router)
app.include_router(routing.router)
app.include_router(admin_bot.router)
app.include_router(places_admin.router)
app.include_router(site_content.router)
app.include_router(analytics.router)
app.include_router(reviews.router)

app.include_router(models_3d.router, prefix="/api")
