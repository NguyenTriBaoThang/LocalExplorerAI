from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=180)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[1]:
            raise ValueError("Enter a valid email address")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[1]:
            raise ValueError("Enter a valid email address")
        return value


class PasswordChangeRequest(BaseModel):
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=180)
    phone: str | None = Field(default=None, max_length=40)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    role: str
    provider_id: str | None
    phone: str | None
    is_active: bool
    email_verified_at: datetime | None = None
    mfa_enabled: bool = False
    created_at: datetime


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if "@" not in value or "." not in value.rsplit("@", 1)[1]:
        raise ValueError("Enter a valid email address")
    return value


class ClaimTicketRequest(BaseModel):
    """``claim_token`` is the single-use secret from the chat-bot link, never the public share token."""

    claim_token: str = Field(min_length=20, max_length=128)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)  # policy is enforced only when a new account is created
    display_name: str | None = Field(default=None, max_length=180)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()  # never reject: the response must not reveal anything about the address


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=128)


class SessionRead(BaseModel):
    id: str                      # the session family id: stable across refresh-token rotations
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    absolute_expires_at: datetime
    ip: str | None
    user_agent: str | None
    amr: list[str]
    current: bool


class MfaChallenge(BaseModel):
    """Returned by login when the account has two-factor authentication: no session exists yet."""

    mfa_required: bool = True
    mfa_ticket: str
    expires_in: int


class MfaLoginRequest(BaseModel):
    mfa_ticket: str = Field(min_length=20, max_length=128)
    code: str = Field(min_length=6, max_length=32)


class MfaCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class MfaDisableRequest(BaseModel):
    password: str | None = Field(default=None, max_length=128)
    code: str = Field(min_length=6, max_length=32)
