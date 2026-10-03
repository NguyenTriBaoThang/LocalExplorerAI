from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.services.rate_limit import ping_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness() -> dict[str, str]:
    checks = {"database": "ok", "redis": "not_required"}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"code": "DATABASE_UNAVAILABLE", "message": "Database readiness check failed."}) from exc
    if settings.rate_limit_enabled:
        if not ping_redis():
            raise HTTPException(status_code=503, detail={"code": "REDIS_UNAVAILABLE", "message": "Rate limiting dependency is unavailable."})
        checks["redis"] = "ok"
    return {"status": "ready", **checks}
