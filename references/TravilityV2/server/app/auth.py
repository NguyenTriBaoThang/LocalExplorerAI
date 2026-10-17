import datetime as dt

import bcrypt
import jwt
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.config import settings
from app.db import READ_ONLY, SHARD_DOWN, get_conn, shard_conn

router = APIRouter(prefix="/auth")
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, v: str) -> str:
        if len(v.encode()) > 72:
            raise ValueError("Mật khẩu tối đa 72 byte (khoảng 24 ký tự có dấu)")
        return v


def make_token(user_id: int) -> str:
    exp = dt.datetime.now(dt.UTC) + dt.timedelta(days=7)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.jwt_secret, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> int:
    if cred is None:
        raise HTTPException(401, "Cần đăng nhập")
    try:
        return int(jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])["sub"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Phiên đăng nhập hết hạn, đăng nhập lại nhé") from None


def get_shard(user_id: int = Depends(current_user)):
    """Kết nối tới shard của User đang đăng nhập; shard chết → 503 chỉ cho User của shard đó (spec scale §10)."""
    try:
        conn = shard_conn(user_id)
    except psycopg.OperationalError:
        raise HTTPException(503, SHARD_DOWN) from None
    try:
        yield conn
    finally:
        conn.close()


@router.post("/register", status_code=201)
def register(body: Credentials, conn=Depends(get_conn)):
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    try:
        row = conn.execute("INSERT INTO users(email, password_hash) VALUES (%s, %s) RETURNING id",
                           (body.email.lower(), pw_hash)).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Email đã được đăng ký") from None
    except psycopg.errors.ReadOnlySqlTransaction:  # get_conn đã lùi về bản sao: node chính chết
        raise HTTPException(503, READ_ONLY) from None
    return {"token": make_token(row["id"])}


@router.post("/login")
def login(body: Credentials, conn=Depends(get_conn)):
    row = conn.execute("SELECT id, password_hash FROM users WHERE email = %s", (body.email.lower(),)).fetchone()
    if not row or not bcrypt.checkpw(body.password.encode(), row["password_hash"].encode()):
        raise HTTPException(401, "Sai email hoặc mật khẩu")
    return {"token": make_token(row["id"])}


@router.get("/me")
def me(user_id: int = Depends(current_user)):
    return {"id": user_id}
