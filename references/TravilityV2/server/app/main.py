from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import auth, group_reviews, nodes, proposals, system, trips, versions
from app.config import settings
from app.db import init_schemas
from app.places_client import PLACES_DOWN, PlacesDown, list_destinations

_DEFAULT_JWT_SECRETS = {"dev-secret-change-me", "doi-chuoi-nay-thanh-chuoi-ngau-nhien-dai"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.jwt_secret in _DEFAULT_JWT_SECRETS:
        raise RuntimeError("JWT_SECRET chưa được đặt — sửa server/.env")
    init_schemas()
    nodes.start("api")
    if settings.places_url:  # nạp sẵn Destination: places chết sau đó thì danh sách và mở Trip vẫn chạy (spec S27)
        try:
            list_destinations(None)
        except PlacesDown:
            pass
    yield


app = FastAPI(title="Travility", lifespan=lifespan)
# Client desktop gửi JWT qua header, không dùng cookie → cho mọi origin là an toàn.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Job-Id"])
app.include_router(auth.router)
app.include_router(trips.router)
app.include_router(group_reviews.router)
app.include_router(proposals.router)
app.include_router(versions.router)
app.include_router(system.router)


@app.exception_handler(PlacesDown)
def places_down(_request, _exc):
    return JSONResponse({"detail": PLACES_DOWN}, status_code=503)


@app.get("/health")
def health():
    return {"ok": True}
