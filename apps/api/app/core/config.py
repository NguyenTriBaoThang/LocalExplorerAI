from functools import lru_cache
import ipaddress
import os
import re
from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve()
_API_ROOT = _CONFIG_PATH.parents[2]
_PROJECT_ROOT = next(
    (
        parent for parent in _CONFIG_PATH.parents
        if (parent / "apps" / "api").is_dir() and (parent / "models").is_dir()
    ),
    _API_ROOT,
)
_REPO_ROOT_ENV = _PROJECT_ROOT / ".env"
_API_DIR_ENV = _API_ROOT / ".env"


def _default_ranker_model_dir() -> str:
    mounted_model_dir = Path("/models/ai-ranker")
    if os.name != "nt" and mounted_model_dir.is_dir():
        return str(mounted_model_dir)
    return str(_PROJECT_ROOT / "models" / "ai-ranker")


class Settings(BaseSettings):
    meshy_api_key: str = ""
    meshy_daily_credits: int = 120
    meshy_storage_dir: str = ""
    app_env: str = "development"
    real_data_only: bool = True
    database_url: str = "sqlite:///./local_explorer.sqlite3"
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_enabled: bool = False
    rate_limit_general_per_minute: int = Field(default=120, ge=1, le=10000)
    rate_limit_auth_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_chat_per_minute: int = Field(default=20, ge=1, le=10000)
    rate_limit_costly_per_minute: int = Field(default=30, ge=1, le=10000)  # geocoding and local ML inference
    rate_limit_prefix: str = "local-explorer:rl"
    trusted_proxy_ips: str = ""
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "Local Explorer AI"
    smtp_starttls: bool = True
    smtp_use_ssl: bool = False
    notification_max_attempts: int = Field(default=5, ge=1, le=20)
    notification_poll_seconds: float = Field(default=5.0, ge=0.5, le=300.0)
    cors_origins: str = "http://localhost:8080,http://localhost:5173,http://127.0.0.1:8080,http://localhost:8081"
    routing_provider: str = "goong"
    geocoding_provider: str = "goong"
    goong_api_key: str | None = None
    goong_maptiles_api_key: str | None = None
    goong_api_base_url: str = "https://rsapi.goong.io"
    goong_timeout_seconds: float = 8.0
    goong_eta_ttl_seconds: int = 300
    geocode_cache_ttl_seconds: int = 86400
    # Open-Meteo's public endpoint is for non-commercial use; production can point at a paid customer endpoint.
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_air_quality_url: str = "https://air-quality-api.open-meteo.com/v1/air-quality"
    open_meteo_api_key: str | None = None
    open_meteo_cache_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    web_push_vapid_public_key: str | None = None
    web_push_vapid_private_key: str | None = None
    web_push_vapid_subject: str | None = None
    web_push_allowed_hosts: str = "fcm.googleapis.com,push.services.mozilla.com,push.apple.com,web.push.apple.com,notify.windows.com,wns.windows.com,push.samsung.com"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-2.5-flash"
    llm_provider: Literal["openai", "gemini"] = "openai"
    openai_timeout_seconds: float = 30.0
    llm_fallback_enabled: bool = False
    app_signing_secret: str | None = None
    # New auth (see docs/auth-design.md). RS256 keys are base64-encoded PEM in the environment, in every
    # environment: generate them with `python -m scripts.generate_auth_keys`.
    auth_issuer: str = "local-explorer-ai"
    auth_audience: str = "local-explorer-api"
    auth_jwt_key_id: str | None = None
    auth_jwt_private_key_b64: str | None = None
    auth_jwt_public_keys_b64: str | None = None  # JSON {"kid": "<base64 pem>"} for retired keys still honoured
    auth_access_ttl_seconds: int = 900
    auth_refresh_ttl_seconds: int = 7 * 24 * 3600
    auth_admin_refresh_ttl_seconds: int = 24 * 3600
    auth_absolute_ttl_seconds: int = 30 * 24 * 3600
    auth_admin_absolute_ttl_seconds: int = 7 * 24 * 3600
    auth_refresh_grace_seconds: int = 10
    auth_refresh_threshold_seconds: int = 180
    # Wrong-password throttling, counted from auth_events (works across workers, no Redis needed).
    auth_login_window_seconds: int = 900
    auth_login_max_failures_per_account_ip: int = Field(default=5, ge=1)   # one e-mail from one address
    auth_login_max_failures_per_account: int = Field(default=20, ge=1)     # one e-mail from anywhere
    auth_login_max_failures_per_ip: int = Field(default=50, ge=1)          # one address against any e-mail
    # The old X-Provider-Access-Key is deprecated. None means "off in production, on elsewhere".
    allow_provider_access_key: bool | None = None
    # Administrators must pass a second factor. None means "on in production, off elsewhere" (handy for demos and local work).
    admin_mfa_required: bool | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    web_app_url: str = "http://localhost:8080"
    # Partner/admin portal. Account emails for provider and admin users link here; empty falls back to web_app_url.
    portal_app_url: str = ""
    vnpay_environment: Literal["sandbox", "production"] = "sandbox"
    vnpay_tmn_code: str | None = None
    vnpay_hash_secret: str | None = None
    vnpay_payment_url: str = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    vnpay_return_url: str | None = None
    vnpay_ipn_url: str | None = None
    payment_provider: Literal["vnpay", "momo"] = "vnpay"
    momo_environment: Literal["sandbox", "production"] = "sandbox"
    momo_partner_code: str | None = None
    momo_access_key: str | None = None
    momo_secret_key: str | None = None
    momo_api_url: str = "https://test-payment.momo.vn/v2/gateway/api/create"
    momo_return_url: str | None = None
    momo_ipn_url: str | None = None
    integration_secrets_key: str | None = None
    demo_admin_email: str = "localexplorerai@admin.com"
    demo_admin_password: str | None = None
    demo_traveler_email: str = "baothang@gmail.com"
    demo_traveler_password: str | None = None
    e5_model_path: str | None = None
    ranker_model_dir: str | None = Field(default_factory=_default_ranker_model_dir)
    enable_bootstrap_ranker: bool = False
    flood_model_dir: str | None = None

    model_config = SettingsConfigDict(env_file=(str(_REPO_ROOT_ENV), str(_API_DIR_ENV), ".env"), extra="ignore")

    @model_validator(mode="after")
    def production_defaults(self):
        """Safer defaults in production unless the operator chose explicitly (an explicit value, either way, always wins)."""
        production = self.app_env.lower() == "production"
        if "rate_limit_enabled" not in self.model_fields_set and production:
            self.rate_limit_enabled = True
        if self.allow_provider_access_key is None:
            self.allow_provider_access_key = not production
        if self.admin_mfa_required is None:
            self.admin_mfa_required = production
        return self

    @model_validator(mode="after")
    def validate_smtp_transport(self):
        if self.smtp_use_ssl and self.smtp_starttls:
            raise ValueError("Set only one SMTP transport mode: SMTP_USE_SSL or SMTP_STARTTLS.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_is_configured(self) -> bool:
        return bool(
            self.openai_api_key and self.openai_api_key.strip()
            and self.openai_base_url.strip()
            and self.openai_model.strip()
        )

    @property
    def email_is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from_email)

    @property
    def web_push_is_configured(self) -> bool:
        subject = (self.web_push_vapid_subject or "").strip()
        return bool(
            self.web_push_vapid_public_key and self.web_push_vapid_public_key.strip()
            and self.web_push_vapid_private_key and self.web_push_vapid_private_key.strip()
            and (subject.startswith("mailto:") or subject.startswith("https://"))
        )

    @property
    def web_push_host_suffixes(self) -> list[str]:
        return [host.strip().lower().rstrip(".") for host in self.web_push_allowed_hosts.split(",") if host.strip()]

    @property
    def vnpay_credentials_configured(self) -> bool:
        return bool(
            self.vnpay_tmn_code and self.vnpay_tmn_code.strip()
            and self.vnpay_hash_secret and self.vnpay_hash_secret.strip()
        )

    @property
    def vnpay_checkout_enabled(self) -> bool:
        if not self.vnpay_credentials_configured or not self.vnpay_return_url or not self.vnpay_ipn_url:
            return False
        if not re.fullmatch(r"[A-Za-z0-9]{8}", self.vnpay_tmn_code or ""):
            return False
        try:
            payment = urlparse(self.vnpay_payment_url.strip())
            return_url = urlparse(self.vnpay_return_url.strip())
            ipn_url = urlparse(self.vnpay_ipn_url.strip())
            payment_host = payment.hostname
            return_host = return_url.hostname
            ipn_host = ipn_url.hostname
        except ValueError:
            return False
        if payment.scheme != "https" or not payment.netloc or payment.query:
            return False
        if (
            not return_url.netloc or not ipn_url.netloc
            or return_url.scheme != "https" or ipn_url.scheme != "https"
            or return_url.path != "/api/payments/vnpay/return"
            or ipn_url.path != "/api/payments/vnpay/ipn"
            or return_url.query or ipn_url.query or return_url.username or ipn_url.username
            or return_url.password or ipn_url.password or return_url.fragment or ipn_url.fragment
            or payment.username or payment.password or payment.fragment
        ):
            return False
        if not _public_https_host(return_host) or not _public_https_host(ipn_host):
            return False
        if self.vnpay_environment == "sandbox" and payment_host != "sandbox.vnpayment.vn":
            return False
        if self.vnpay_environment == "production" and payment_host == "sandbox.vnpayment.vn":
            return False
        if self.app_env.lower() in {"prod", "production"}:
            return (
                self.vnpay_environment == "production"
                and payment_host != "sandbox.vnpayment.vn"
            )
        return True


def _public_https_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid", ".example")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return "." in host


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
