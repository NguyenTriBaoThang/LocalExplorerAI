"""Signed, expiring binding between a chat preview and its confirmation."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.schemas.planner import PlanRequest


_DEVELOPMENT_SECRET = secrets.token_urlsafe(48)
PREVIEW_TTL_SECONDS = 600


class InvalidPlanPreviewToken(ValueError):
    pass


def _secret() -> bytes:
    if settings.app_signing_secret:
        return settings.app_signing_secret.encode("utf-8")
    if settings.app_env.lower() in {"development", "test"}:
        return _DEVELOPMENT_SECRET.encode("utf-8")
    raise RuntimeError("APP_SIGNING_SECRET must be configured for itinerary previews.")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def request_fingerprint(request: PlanRequest) -> str:
    return hashlib.sha256(_canonical(request.model_dump(mode="json"))).hexdigest()


def plan_fingerprint(result: dict[str, Any]) -> str:
    route_fields = (
        "from_experience_id", "to_experience_id", "from_label", "to_label", "distance_m",
        "duration_min", "provider", "is_realtime", "eta_source", "eta_source_uri", "geometry",
    )
    reviewed_plan = {
        "status": result.get("feasibility_status"),
        "estimated_cost_vnd": result.get("estimated_cost_vnd"),
        "total_travel_min": result.get("total_travel_min"),
        "start_at": result.get("start_at"),
        "return_deadline": result.get("return_deadline"),
        "estimated_return_at": result.get("estimated_return_at"),
        "origin": [result.get("origin_label"), result.get("origin_latitude"), result.get("origin_longitude")],
        "destination": [result.get("destination_label"), result.get("destination_latitude"), result.get("destination_longitude")],
        "stops": [
            {
                key: stop.get(key)
                for key in (
                    "position", "experience_id", "slot_id", "name", "arrival_at", "start_at", "end_at",
                    "cost_vnd", "availability_status", "availability_known", "data_status",
                )
            } | {"poi": stop.get("poi")} for stop in result.get("stops", [])
        ],
        # Freshness timestamps change on each solve; the reviewed path and ETA do not.
        "routes": [
            {key: route.get(key) for key in route_fields}
            for route in result.get("routes", [])
        ],
    }
    return hashlib.sha256(_canonical(reviewed_plan)).hexdigest()


def issue_plan_preview_token(request: PlanRequest, result: dict[str, Any], owner_id: str | None) -> tuple[str, str]:
    payload = {
        "purpose": "itinerary-preview",
        "expires_at": int(time.time()) + PREVIEW_TTL_SECONDS,
        "owner_id": owner_id,
        "request_fingerprint": request_fingerprint(request),
        "plan_fingerprint": plan_fingerprint(result),
    }
    body = base64.urlsafe_b64encode(_canonical(payload)).decode("ascii").rstrip("=")
    signature = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    token = f"{body}.{base64.urlsafe_b64encode(signature).decode('ascii').rstrip('=')}"
    return str(uuid4()), token


def verify_plan_preview_token(token: str, owner_id: str | None) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
        actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as error:
        raise InvalidPlanPreviewToken("The preview token is malformed.") from error
    if not hmac.compare_digest(actual, expected):
        raise InvalidPlanPreviewToken("The preview token signature is invalid.")
    if not isinstance(payload, dict) or payload.get("purpose") != "itinerary-preview":
        raise InvalidPlanPreviewToken("The token is not an itinerary preview confirmation.")
    if not isinstance(payload.get("expires_at"), int) or payload["expires_at"] <= int(time.time()):
        raise InvalidPlanPreviewToken("The itinerary preview has expired.")
    if payload.get("owner_id") != owner_id:
        raise InvalidPlanPreviewToken("The itinerary preview belongs to a different traveler.")
    return payload
