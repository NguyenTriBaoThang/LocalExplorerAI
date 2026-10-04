from functools import lru_cache
import ipaddress
import re
from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


from pathlib import Path
_REPO_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"
_API_DIR_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    app_env: str = "development"
    real_data_only: bool = True
    database_url: str = "sqlite:///./local_explorer.sqlite3"
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_enabled: bool = False
    rate_limit_general_per_minute: int = Field(default=120, ge=1, le=10000)
    rate_limit_auth_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_chat_per_minute: int = Field(default=20, ge=1, le=10000)
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
    cors_origins: str = "http://localhost:5173"
    routing_provider: str = "goong"
    geocoding_provider: str = "goong"
    goong_api_key: str | None = None
    goong_maptiles_api_key: str | None = None
    goong_api_base_url: str = "https://rsapi.goong.io"
    goong_timeout_seconds: float = 8.0
    goong_eta_ttl_seconds: int = 300
    geocode_cache_ttl_seconds: int = 86400
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-2.5-flash"
    llm_provider: Literal["openai", "gemini"] = "openai"
    openai_timeout_seconds: float = 30.0
    llm_fallback_enabled: bool = False
    admin_api_key: str | None = None
    app_signing_secret: str | None = None
    auth_secret: str | None = None
    session_ttl_seconds: int = 7200
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    web_app_url: str = "http://localhost:5173"
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
    ranker_model_dir: str | None = None
    flood_model_dir: str | None = None
    allow_unverified_ranker: bool = False

    model_config = SettingsConfigDict(env_file=(str(_REPO_ROOT_ENV), str(_API_DIR_ENV), ".env"), extra="ignore")

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
