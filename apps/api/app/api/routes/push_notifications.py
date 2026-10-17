"""Authenticated Web Push subscription management for booking updates."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.guards import public, require_user
from app.api.permissions import P
from app.core.config import settings
from app.models.entities import User, WebPushSubscription

router = APIRouter(prefix="/api/notifications/push", tags=["push notifications"])


class SubscriptionKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(min_length=20, max_length=256)
    auth: str = Field(min_length=12, max_length=128)


class PushSubscriptionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=30, max_length=2048)
    keys: SubscriptionKeys


class PushUnsubscribePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=30, max_length=2048)


def _configured() -> None:
    if not settings.web_push_is_configured:
        raise HTTPException(status_code=503, detail={
            "code": "WEB_PUSH_NOT_CONFIGURED",
            "message": "Web Push is not configured for this environment.",
        })


def _validate_endpoint(endpoint: str) -> str:
    try:
        parsed = urlsplit(endpoint)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_PUSH_ENDPOINT", "message": "Invalid push endpoint."}) from error
    allowed = any(host == suffix or host.endswith("." + suffix) for suffix in settings.web_push_host_suffixes)
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or parsed.fragment or port not in (None, 443)
            or not allowed or not re.fullmatch(r"[A-Za-z0-9._~:/?&=%+-]+", endpoint)):
        raise HTTPException(status_code=422, detail={
            "code": "INVALID_PUSH_ENDPOINT",
            "message": "The push endpoint must use HTTPS and belong to a supported browser push service.",
        })
    return endpoint


@router.get("/vapid-public-key", dependencies=[Depends(public("the VAPID application-server public key is public by design"))])
def vapid_public_key():
    _configured()
    return {"public_key": settings.web_push_vapid_public_key}


@router.get("/status")
def push_status(user: User = Depends(require_user(P.ACCOUNT_READ)), db: Session = Depends(get_db)):
    active = db.scalar(select(func.count(WebPushSubscription.id)).where(
        WebPushSubscription.user_id == user.id,
        WebPushSubscription.is_active.is_(True),
    )) or 0
    return {"configured": settings.web_push_is_configured, "enabled": active > 0, "device_count": active}


@router.post("/subscriptions", status_code=201)
def save_push_subscription(
    payload: PushSubscriptionPayload,
    user: User = Depends(require_user(P.ACCOUNT_READ)),
    db: Session = Depends(get_db),
):
    _configured()
    endpoint = _validate_endpoint(payload.endpoint)
    for value in (payload.keys.p256dh, payload.keys.auth):
        if not re.fullmatch(r"[A-Za-z0-9_-]+=*", value):
            raise HTTPException(status_code=422, detail={"code": "INVALID_PUSH_KEYS", "message": "Invalid push encryption keys."})

    subscription = db.scalar(select(WebPushSubscription).where(WebPushSubscription.endpoint == endpoint))
    if subscription is None:
        subscription = WebPushSubscription(
            user_id=user.id,
            endpoint=endpoint,
            p256dh_key=payload.keys.p256dh,
            auth_key=payload.keys.auth,
            is_active=True,
        )
        db.add(subscription)
    else:
        # A browser subscription belongs to the account currently signed in on that device.
        subscription.user_id = user.id
        subscription.p256dh_key = payload.keys.p256dh
        subscription.auth_key = payload.keys.auth
        subscription.is_active = True
        subscription.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"enabled": True}


@router.delete("/subscriptions")
def delete_push_subscription(
    payload: PushUnsubscribePayload,
    user: User = Depends(require_user(P.ACCOUNT_READ)),
    db: Session = Depends(get_db),
):
    endpoint = _validate_endpoint(payload.endpoint)
    subscription = db.scalar(select(WebPushSubscription).where(
        WebPushSubscription.endpoint == endpoint,
        WebPushSubscription.user_id == user.id,
    ))
    if subscription is not None:
        db.delete(subscription)
        db.commit()
    return {"enabled": db.scalar(select(func.count(WebPushSubscription.id)).where(
        WebPushSubscription.user_id == user.id,
        WebPushSubscription.is_active.is_(True),
    )) > 0}
