"""Meshy transport and restart-safe polling. Never replay billable POST requests."""
import asyncio
import json
import struct
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from sqlalchemy import select
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import MeshyJob
from app.services.integration_config import resolve_integration_value

BASE = "https://api.meshy.ai"
ACTIVE = {"pending", "running"}
MAX_BYTES = 50 * 1024 * 1024

def now():
    return datetime.now(timezone.utc)

def root():
    return Path(settings.meshy_storage_dir) if settings.meshy_storage_dir else Path(__file__).resolve().parents[2] / ".meshy-assets"

def asset(job_id):
    from uuid import UUID
    return root() / str(UUID(job_id)) / "model.glb"

def endpoint(kind):
    return "/openapi/v1/multi-image-to-3d" if kind == "image" else "/openapi/v2/text-to-3d"

def key(db):
    return resolve_integration_value(db, "meshy", "api_key")

def request(db, method, path, payload=None):
    secret = key(db)
    if not secret:
        raise ValueError("Chưa cấu hình Meshy API key trong Tích hợp.")
    with httpx.Client(timeout=25, follow_redirects=False) as client:
        response = client.request(method, BASE + path, headers={"Authorization": "Bearer " + secret}, json=payload)
        response.raise_for_status()
        return response.json()

def validate_glb(data):
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("Tệp không phải GLB hợp lệ")
    version, length, chunk_len, chunk_type = struct.unpack_from("<IIII", data, 4)
    if version != 2 or length != len(data) or chunk_type != 0x4E4F534A or chunk_len > len(data) - 20:
        raise ValueError("GLB hỏng hoặc không hỗ trợ")
    doc = json.loads(data[20:20 + chunk_len])
    # Disallow remote dependencies: preview must not cause arbitrary browser requests.
    for item in doc.get("buffers", []) + doc.get("images", []):
        if item.get("uri") and not item["uri"].startswith("data:"):
            raise ValueError("GLB phải nhúng texture và buffer")

def download(url, job_id):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "assets.meshy.ai" or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError("Địa chỉ tải model không hợp lệ")
    data = bytearray()
    with httpx.stream("GET", url, timeout=60, follow_redirects=False) as response:
        response.raise_for_status()
        for part in response.iter_bytes():
            data.extend(part)
            if len(data) > MAX_BYTES:
                raise ValueError("Model vượt giới hạn 50 MB")
    validate_glb(data)
    target = asset(job_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_bytes(data)
    temp.replace(target)

def calibration(row, private=False):
    return {"pitch": 0, "roll": 0, **{k: v for k, v in row.metadata_json.items() if k in {"display_name", "poi_id", "latitude", "longitude", "scale", "heading", "altitude", "pitch", "roll"}}, "model_name": "meshy-" + row.id,
            "file_url": f"/api/{'admin/' if private else ''}meshy/jobs/{row.id}/asset",
            "description": "Mô hình do AI tạo · Cần đối chiếu với công trình thực tế.",
            "updated_at": row.updated_at.isoformat()}

def tick():
    with SessionLocal() as db:
        ids = list(db.scalars(select(MeshyJob.id).where(MeshyJob.status.in_(ACTIVE | {"submitting"}))))
    for job_id in ids:
        with SessionLocal() as db:
            row = db.scalar(select(MeshyJob).where(MeshyJob.id == job_id).with_for_update(skip_locked=True))
            if not row or row.status not in ACTIVE | {"submitting"}:
                continue
            if row.status == "submitting":
                if now() - row.updated_at > timedelta(minutes=2):
                    row.status, row.error = "uncertain", "Không rõ yêu cầu đã được Meshy nhận chưa. Kiểm tra dashboard Meshy trước khi tạo lại."
                    db.commit()
                continue
            if now() > datetime.fromisoformat(row.metadata_json.get("poll_deadline", (row.created_at + timedelta(hours=2)).isoformat())):
                row.status, row.error = "timeout", "Quá thời gian theo dõi. Kiểm tra Meshy rồi bấm Tiếp tục kiểm tra; không tạo tác vụ mới."
                db.commit()
                continue
            try:
                result = request(db, "GET", endpoint(row.kind) + "/" + row.task_id)
                status = result.get("status")
                row.progress = max(0, min(100, int(result.get("progress", 0))))
                if status == "SUCCEEDED":
                    download(result["model_urls"]["glb"], row.id)
                    row.status, row.progress, row.error = "ready", 100, None
                elif status in {"FAILED", "CANCELED", "EXPIRED"}:
                    row.status, row.error = "failed", "Meshy không hoàn thành tác vụ. Xem dashboard Meshy để biết chi tiết."
                else:
                    row.status = "running"
                    row.error = None
            except httpx.HTTPStatusError as exc:
                row.error = f"Meshy trả HTTP {exc.response.status_code}; sẽ kiểm tra lại, không tạo tác vụ mới."
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                row.error = "Chưa tải được kết quả hợp lệ; hệ thống sẽ kiểm tra lại."
            row.updated_at = now()
            db.commit()

async def worker():
    import logging
    while True:
        try:
            await asyncio.to_thread(tick)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never log upstream URLs, response bodies or credentials.
            logging.getLogger(__name__).warning("Meshy polling unavailable; retrying later")
        await asyncio.sleep(15)
