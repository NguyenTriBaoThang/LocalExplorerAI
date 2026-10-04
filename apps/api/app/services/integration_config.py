"""Allowlisted, encrypted integration configuration shared by admin and runtime."""

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any
from uuid import uuid4
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import IntegrationSecret


class IntegrationSecretConfigurationError(RuntimeError):
    pass


def _development_key_file() -> Path:
    return Path(__file__).resolve().parents[2] / ".local-secrets" / "integration-secrets.key"


def _development_fernet_key() -> str:
    """Create a stable local key for development; production must inject its own key."""
    from cryptography.fernet import Fernet

    key_file = _development_key_file()
    key_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with key_file.open("xb") as stream:
            stream.write(Fernet.generate_key())
        try:
            os.chmod(key_file.parent, 0o700)
            os.chmod(key_file, 0o600)
        except OSError:
            # Windows ACLs inherit from the workspace; production uses an injected key.
            pass
    except FileExistsError:
        pass
    try:
        key = key_file.read_text(encoding="ascii").strip()
        Fernet(key.encode("ascii"))
        return key
    except (OSError, UnicodeEncodeError, ValueError) as error:
        raise IntegrationSecretConfigurationError(
            "The local integration encryption key is unreadable or invalid."
        ) from error


@dataclass(frozen=True)
class IntegrationField:
    label: str
    secret: bool = False
    fallback_setting: str | None = None


INTEGRATION_FIELDS: dict[str, dict[str, IntegrationField]] = {
    "payments": {
        "provider": IntegrationField("Payment provider", fallback_setting="payment_provider"),
        "momo_environment": IntegrationField("MoMo environment", fallback_setting="momo_environment"),
        "momo_partner_code": IntegrationField("MoMo partner code", fallback_setting="momo_partner_code"),
        "momo_access_key": IntegrationField("MoMo access key", secret=True, fallback_setting="momo_access_key"),
        "momo_secret_key": IntegrationField("MoMo secret key", secret=True, fallback_setting="momo_secret_key"),
        "momo_api_url": IntegrationField("MoMo create API URL", fallback_setting="momo_api_url"),
        "momo_return_url": IntegrationField("MoMo return URL", fallback_setting="momo_return_url"),
        "momo_ipn_url": IntegrationField("MoMo IPN URL", fallback_setting="momo_ipn_url"),
        "vnpay_environment": IntegrationField("VNPay environment", fallback_setting="vnpay_environment"),
        "vnpay_tmn_code": IntegrationField("VNPay TMN code", fallback_setting="vnpay_tmn_code"),
        "vnpay_hash_secret": IntegrationField("VNPay hash secret", secret=True, fallback_setting="vnpay_hash_secret"),
        "vnpay_payment_url": IntegrationField("VNPay payment URL", fallback_setting="vnpay_payment_url"),
        "vnpay_return_url": IntegrationField("VNPay return URL", fallback_setting="vnpay_return_url"),
        "vnpay_ipn_url": IntegrationField("VNPay IPN URL", fallback_setting="vnpay_ipn_url"),
    },
    "routing": {
        "provider": IntegrationField("Routing provider", fallback_setting="routing_provider"),
        "geocoding_provider": IntegrationField("Geocoding provider", fallback_setting="geocoding_provider"),
        "goong_api_key": IntegrationField("Goong REST API key (Tuyến đường & Geocode)", secret=True, fallback_setting="goong_api_key"),
        "goong_maptiles_key": IntegrationField("Goong Maptiles key (Hiển thị bản đồ nền & 3D)", secret=True, fallback_setting="goong_maptiles_api_key"),
        "goong_api_base_url": IntegrationField("Goong API base URL", fallback_setting="goong_api_base_url"),
    },
    "ai": {
        "provider": IntegrationField("Chat provider", fallback_setting="llm_provider"),
        "openai_api_key": IntegrationField("OpenAI-compatible API key", secret=True, fallback_setting="openai_api_key"),
        "openai_base_url": IntegrationField("OpenAI-compatible base URL", fallback_setting="openai_base_url"),
        "openai_model": IntegrationField("OpenAI-compatible model", fallback_setting="openai_model"),
        "gemini_api_key": IntegrationField("Gemini API key", secret=True, fallback_setting="gemini_api_key"),
        "gemini_base_url": IntegrationField("Gemini OpenAI-compatible base URL", fallback_setting="gemini_base_url"),
        "gemini_model": IntegrationField("Gemini model", fallback_setting="gemini_model"),
    },
    "google_oauth": {
        "client_id": IntegrationField("Google OAuth client ID", fallback_setting="google_client_id"),
        "client_secret": IntegrationField("Google OAuth client secret", secret=True, fallback_setting="google_client_secret"),
        "redirect_uri": IntegrationField("Google OAuth redirect URI", fallback_setting="google_redirect_uri"),
    },
}


def _fernet():
    key = (settings.integration_secrets_key or "").strip()
    if not key and settings.app_env.lower() == "development":
        key = _development_fernet_key()
        settings.integration_secrets_key = key
    if not key:
        raise IntegrationSecretConfigurationError(
            "Set INTEGRATION_SECRETS_KEY to a persistent Fernet key before storing integration credentials."
        )
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode("ascii"))
    except (ImportError, ValueError, UnicodeEncodeError) as error:
        raise IntegrationSecretConfigurationError(
            "INTEGRATION_SECRETS_KEY is invalid or the cryptography dependency is unavailable."
        ) from error


def _fallback(service: str, key: str) -> str | None:
    field = INTEGRATION_FIELDS[service][key]
    setting_name = field.fallback_setting
    value: Any = getattr(settings, setting_name) if setting_name else None
    return value.strip() if isinstance(value, str) and value.strip() else (str(value) if value is not None else None)


def resolve_integration_value(db: Session | None, service: str, key: str) -> str | None:
    """Prefer the encrypted admin override; otherwise use the environment fallback."""
    fields = INTEGRATION_FIELDS.get(service)
    if fields is None or key not in fields:
        raise KeyError(f"Unknown integration setting: {service}.{key}")
    row = db.scalar(select(IntegrationSecret).where(
        IntegrationSecret.service == service,
        IntegrationSecret.config_key == key,
    )) if db is not None else None
    if row is not None:
        try:
            return _fernet().decrypt(row.encrypted_value.encode("ascii")).decode("utf-8")
        except Exception as error:
            if isinstance(error, IntegrationSecretConfigurationError):
                raise
            raise IntegrationSecretConfigurationError(
                f"The stored integration setting {service}.{key} cannot be decrypted; verify the master key."
            ) from error
    return _fallback(service, key)


def list_integration_settings(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(IntegrationSecret)).all()
    by_name = {(row.service, row.config_key): row for row in rows}
    services: list[dict[str, Any]] = []
    for service, fields in INTEGRATION_FIELDS.items():
        listed_fields = []
        for key, field in fields.items():
            row = by_name.get((service, key))
            value = resolve_integration_value(db, service, key)
            listed_fields.append({
                "key": key,
                "label": field.label,
                "secret": field.secret,
                "configured": bool(value),
                "source": "admin" if row else ("environment" if value else "missing"),
                "value": None if field.secret else value,
                "updated_at": row.updated_at if row else None,
            })
        services.append({"service": service, "fields": listed_fields})
    return services


def update_integration_settings(
    db: Session,
    service: str,
    values: dict[str, str],
    remove_keys: list[str],
    actor_id: str,
) -> tuple[list[str], list[str]]:
    fields = INTEGRATION_FIELDS.get(service)
    if fields is None:
        raise KeyError(service)
    unknown = (set(values) | set(remove_keys)) - set(fields)
    if unknown:
        raise ValueError(f"Unknown setting key(s): {', '.join(sorted(unknown))}")
    if set(values) & set(remove_keys):
        raise ValueError("A setting cannot be updated and removed in the same request.")
    if len(values) + len(remove_keys) > len(fields):
        raise ValueError("Too many integration settings in one request.")

    enum_values = {
        ("payments", "provider"): {"vnpay", "momo"},
        ("payments", "momo_environment"): {"sandbox", "production"},
        ("payments", "vnpay_environment"): {"sandbox", "production"},
        ("routing", "provider"): {"goong", "mock"},
        ("routing", "geocoding_provider"): {"goong"},
        ("ai", "provider"): {"openai", "gemini"},
    }
    for key, value in values.items():
        normalized = value.strip()
        allowed = enum_values.get((service, key))
        if allowed is not None and normalized.lower() not in allowed:
            raise ValueError(f"{key} must be one of: {', '.join(sorted(allowed))}.")
        if any(ord(character) < 32 for character in normalized):
            raise ValueError(f"{key} contains a control character.")
        if service == "routing" and key == "provider" and normalized.lower() == "mock" and settings.real_data_only:
            raise ValueError("Mock routing cannot be enabled while REAL_DATA_ONLY is enabled.")
        if key.endswith(("_url", "_uri", "_base_url")):
            parsed = urlparse(normalized)
            if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError(f"{key} must be an absolute HTTP(S) URL without embedded credentials.")
            if key in {"momo_return_url", "momo_ipn_url", "vnpay_return_url", "vnpay_ipn_url"} and parsed.scheme != "https":
                raise ValueError(f"{key} must use HTTPS.")
            if (service, key) == ("google_oauth", "redirect_uri") and parsed.path != "/api/auth/google/callback":
                raise ValueError("google_redirect_uri must end in /api/auth/google/callback.")

    encrypted = _fernet() if values else None
    updated, removed = [], []
    for key, value in values.items():
        if not isinstance(value, str) or len(value) > 2048 or not value.strip():
            raise ValueError(f"{key} must be a non-empty string of at most 2048 characters.")
        encoded = encrypted.encrypt(value.strip().encode("utf-8")).decode("ascii")
        row = db.scalar(select(IntegrationSecret).where(
            IntegrationSecret.service == service,
            IntegrationSecret.config_key == key,
        ))
        now = datetime.now(timezone.utc)
        if row is None:
            row = IntegrationSecret(
                id=str(uuid4()), service=service, config_key=key,
                encrypted_value=encoded, updated_by=actor_id, created_at=now, updated_at=now,
            )
            db.add(row)
        else:
            row.encrypted_value = encoded
            row.updated_by = actor_id
            row.updated_at = now
        updated.append(key)

    for key in remove_keys:
        row = db.scalar(select(IntegrationSecret).where(
            IntegrationSecret.service == service,
            IntegrationSecret.config_key == key,
        ))
        if row is not None:
            db.delete(row)
        removed.append(key)
    return updated, removed
