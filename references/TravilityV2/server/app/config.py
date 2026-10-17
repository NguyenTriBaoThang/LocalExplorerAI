import datetime as dt
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://travility:travility@localhost:5432/travility"
    jwt_secret: str = "dev-secret-change-me"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    embed_base_url: str = "https://api.openai.com/v1"
    embed_api_key: str = ""
    embed_model: str = "text-embedding-3-small"
    goong_api_key: str = ""
    # Scale (spec 2026-10-01 §4): thiếu biến nào thì phần đó chạy như chế độ một tiến trình.
    redis_url: str = ""
    plan_rpm: int = 5  # việc lập lịch mỗi phút cho một User (cần REDIS_URL); 0 = không giới hạn
    planner_mode: Literal["single", "multi"] = "single"  # multi = 3 agent chuyên gia + tổng hợp (spec §7)
    places_url: str = ""  # có → Place, Destination và km Goong đi qua service places (app/places_service.py)
    catalog_replica_url: str = ""  # có → đọc Place từ bản sao; bản sao chết thì đọc DATABASE_URL
    shard_urls: str = ""  # URL các shard, cách nhau dấu phẩy; có → Trip của User nằm ở shard user_id % N
    demo_today: dt.date | None = None  # đóng băng "hôm nay" để bản ghi replay của llm-gateway trúng cache
    # llm-gateway (app/gateway.py)
    gateway_cache: Literal["off", "on", "replay"] = "on"
    gateway_chat_ttl: int = 86400  # giây; 0 = không hết hạn (ghi kịch bản demo)
    llm_rpm: int = 0  # lượt chat mỗi phút tới provider chính; 0 = không giới hạn
    llm2_base_url: str = ""  # provider phụ cho chat; trống = không chuyển provider
    llm2_api_key: str = ""
    llm2_model: str = ""

    @field_validator("demo_today", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        return v or None

    @field_validator("planner_mode", mode="before")
    @classmethod
    def _blank_is_single(cls, v):
        return v or "single"


settings = Settings()
