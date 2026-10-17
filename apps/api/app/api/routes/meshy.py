"""Admin-only paid generation with private drafts and explicit publication."""
import base64
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict, model_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.guards import require_user, public
from app.api.permissions import P
from app.db.session import get_db
from app.core.config import settings
from app.models.entities import MeshyJob, User, POI, AuditLog
from app.services import meshy

router = APIRouter(prefix="/api", tags=["Meshy 3D"])

class Generate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: UUID
    kind: Literal["text", "image"] = "text"
    display_name: str = Field(min_length=2, max_length=120)
    prompt: str = Field(default="", max_length=800)
    images: list[str] = Field(default_factory=list, max_length=4)
    poi_id: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    scale: float = Field(default=20, gt=0.5, le=1000)
    heading: float = Field(default=0, ge=0, lt=360)
    altitude: float = Field(default=0, ge=-50, le=200)
    max_credits: int = Field(ge=0, le=30)

    @model_validator(mode="after")
    def validate_inputs(self):
        if self.kind == "text" and (not self.prompt.strip() or self.images):
            raise ValueError("Nhập mô tả; ảnh chỉ dùng ở chế độ ảnh")
        if self.kind == "image" and not self.images:
            raise ValueError("Chọn 1–4 ảnh")
        for image in self.images:
            header, _, encoded = image.partition(",")
            if header not in {"data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"} or len(encoded) > 7_000_000:
                raise ValueError("Ảnh phải là PNG/JPEG/WebP, tối đa 5 MB")
            try:
                raw = base64.b64decode(encoded, validate=True)
            except ValueError:
                raise ValueError("Ảnh không hợp lệ")
            valid = (header == "data:image/png;base64" and raw.startswith(b"\x89PNG\r\n\x1a\n")) or (header == "data:image/jpeg;base64" and raw.startswith(b"\xff\xd8\xff")) or (header == "data:image/webp;base64" and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP")
            if not valid or len(raw) > 5 * 1024 * 1024:
                raise ValueError("Ảnh không hợp lệ hoặc quá 5 MB")
        return self

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=16)
    images: list[str] = Field(default_factory=list, max_length=4)
    place_name: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def validate_chat(self):
        if self.messages[-1].role != "user":
            raise ValueError("Tin nhắn cuối phải là của người dùng")
        if self.images:
            Generate(request_key=uuid4(), kind="image", display_name="Chat images", images=self.images,
                     latitude=0, longitude=0, max_credits=30)
        return self

@router.post("/admin/meshy/chat")
def chat(body: ChatRequest, actor: User = Depends(require_user(P.ADMIN_MODELS_3D)), db: Session = Depends(get_db)):
    from app.services.meshy_assistant import prepare
    try:
        return prepare(db, body.messages, body.images, body.place_name)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))

class PaidAction(BaseModel):
    request_key: UUID
    max_credits: int = Field(ge=0, le=10)

class Placement(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    scale: float = Field(gt=0.5, le=1000)
    heading: float = Field(ge=0, lt=360)
    altitude: float = Field(ge=-50, le=200)
    pitch: float = Field(default=0, ge=-90, le=90)
    roll: float = Field(default=0, ge=-90, le=90)

def get_job(db, job_id):
    row = db.scalar(select(MeshyJob).where(MeshyJob.id == str(job_id)).with_for_update())
    if not row:
        raise HTTPException(404, "Không tìm thấy tác vụ")
    return row

def view(row):
    return {"id": row.id, "task_id": row.task_id, "kind": row.kind, "status": row.status,
            "progress": row.progress, "credits": row.credits, "error": row.error,
            "published": row.published, "previewed": row.previewed_at is not None,
            "created_at": row.created_at, "calibration": meshy.calibration(row, private=True)}

def audit(db, actor, row, action):
    db.add(AuditLog(id=str(uuid4()), actor_id=actor.id, action="meshy." + action,
        target_type="meshy_job", target_id=row.id, details={"credits": row.credits}, created_at=meshy.now()))

def reserve(db, actor, request_key, cost, maximum, kind, metadata, parent=None):
    # Serialize per-account reservations so concurrent clicks cannot bypass budget.
    db.scalar(select(User).where(User.id == actor.id).with_for_update())
    existing = db.scalar(select(MeshyJob).where(MeshyJob.request_key == str(request_key)))
    if existing:
        if existing.actor_id != actor.id:
            raise HTTPException(409, "Mã yêu cầu đã được dùng")
        return existing, False
    if parent:
        existing = db.scalar(select(MeshyJob).where(MeshyJob.parent_id == parent))
        if existing:
            return existing, False
    if maximum < cost:
        raise HTTPException(422, "Cần xác nhận đủ credit cho tác vụ")
    if not meshy.key(db):
        raise HTTPException(422, "Nhập Meshy API key mới tại Tích hợp & API keys trước")
    today = meshy.now().replace(hour=0, minute=0, second=0, microsecond=0)
    used = db.scalar(select(func.coalesce(func.sum(MeshyJob.credits), 0)).where(MeshyJob.actor_id == actor.id, MeshyJob.created_at >= today))
    active = db.scalar(select(func.count()).select_from(MeshyJob).where(MeshyJob.actor_id == actor.id, MeshyJob.status.in_({"submitting", "pending", "running", "uncertain"})))
    if used + cost > settings.meshy_daily_credits or active >= 2:
        raise HTTPException(429, "Đã đạt hạn mức ngày hoặc đang có 2 tác vụ chưa hoàn tất")
    row = MeshyJob(id=str(uuid4()), actor_id=actor.id, request_key=str(request_key), parent_id=parent,
                  kind=kind, credits=cost, metadata_json=metadata, status="submitting", progress=0)
    db.add(row)
    audit(db, actor, row, "reserved")
    db.commit()  # Persist BEFORE sending the paid request.
    return row, True

def submit(db, row, payload):
    try:
        result = meshy.request(db, "POST", meshy.endpoint(row.kind), payload)
        task_id = result.get("result")
        if not isinstance(task_id, str) or len(task_id) > 100 or not all(c.isalnum() or c == "-" for c in task_id):
            raise ValueError("Invalid task id")
        row.task_id, row.status = task_id, "pending"
    except httpx.HTTPStatusError as exc:
        row.status = "failed" if 400 <= exc.response.status_code < 500 else "uncertain"
        row.error = f"Meshy trả HTTP {exc.response.status_code}. Kiểm tra dashboard trước khi tạo lại."
    except (httpx.HTTPError, ValueError):
        row.status, row.error = "uncertain", "Chưa xác định Meshy đã nhận yêu cầu. Không tự gửi lại để tránh trừ credit hai lần."
    row.updated_at = meshy.now()
    db.commit()
    return view(row)

@router.get("/admin/meshy/jobs")
def jobs(actor: User = Depends(require_user(P.ADMIN_MODELS_3D)), db: Session = Depends(get_db)):
    rows = db.scalars(select(MeshyJob).order_by(MeshyJob.created_at.desc()).limit(100))
    return {"configured": bool(meshy.key(db)), "daily_limit": settings.meshy_daily_credits, "jobs": [view(r) for r in rows], "places": [{"id": p.id, "name": p.name, "latitude": p.latitude, "longitude": p.longitude} for p in db.scalars(select(POI).order_by(POI.name).limit(500))]}

@router.post("/admin/meshy/jobs")
def generate(body: Generate, actor: User = Depends(require_user(P.ADMIN_MODELS_3D)), db: Session = Depends(get_db)):
    metadata = body.model_dump(exclude={"request_key", "kind", "images", "max_credits"})
    if body.poi_id:
        poi = db.get(POI, body.poi_id)
        if not poi:
            raise HTTPException(422, "Địa điểm không tồn tại")
        metadata.update(latitude=poi.latitude, longitude=poi.longitude)
    cost = 20 if body.kind == "text" else 30
    row, fresh = reserve(db, actor, body.request_key, cost, body.max_credits, body.kind, metadata)
    if not fresh:
        return view(row)
    payload = {"ai_model": "meshy-6", "target_formats": ["glb"], "should_remesh": True, "target_polycount": 30000}
    if body.kind == "text":
        payload.update(mode="preview", prompt=body.prompt)
    else:
        payload.update(image_urls=body.images, should_texture=True)
    return submit(db, row, payload)

@router.post("/admin/meshy/jobs/{job_id}/refine")
def refine(job_id: UUID, body: PaidAction, actor: User = Depends(require_user(P.ADMIN_MODELS_3D)), db: Session = Depends(get_db)):
    parent = get_job(db, job_id)
    if parent.status != "ready" or parent.kind != "text":
        raise HTTPException(409, "Chỉ tạo texture cho bản hình học đã hoàn tất")
    row, fresh = reserve(db, actor, body.request_key, 10, body.max_credits, "refine", parent.metadata_json, parent.id)
    return submit(db, row, {"mode": "refine", "preview_task_id": parent.task_id, "ai_model": "meshy-6", "texture_resolution": "2k", "target_formats": ["glb"]}) if fresh else view(row)

class Reconcile(BaseModel):
    task_id: UUID | None = None
    confirmed_not_created: bool = False

@router.post("/admin/meshy/jobs/{job_id}/reconcile")
def reconcile(job_id: UUID, body: Reconcile, actor: User = Depends(require_user(P.ADMIN_MODELS_3D)), db: Session = Depends(get_db)):
    row = get_job(db, job_id)
    if row.status != "uncertain":
        raise HTTPException(409, "Chỉ đối chiếu tác vụ chưa rõ trạng thái")
    if body.task_id:
        try:
            result = meshy.request(db, "GET", meshy.endpoint(row.kind) + "/" + str(body.task_id))
        except (httpx.HTTPError, ValueError):
            raise HTTPException(422, "Không tìm thấy tác vụ này trong tài khoản Meshy đã cấu hình")
        expected = {"text": "text-to-3d-preview", "refine": "text-to-3d-refine", "image": "multi-image-to-3d"}[row.kind]
        if result.get("type") != expected:
            raise HTTPException(422, "Loại tác vụ Meshy không khớp")
        row.task_id, row.status, row.error = str(body.task_id), "pending", None
        row.metadata_json = {**row.metadata_json, "poll_deadline": (meshy.now() + timedelta(hours=2)).isoformat()}
    elif body.confirmed_not_created:
        row.status, row.error = "failed", "Quản trị viên đã đối chiếu: Meshy không tạo tác vụ. Credit dự phòng vẫn tính trong hạn mức ngày."
    else:
        raise HTTPException(422, "Nhập task ID hoặc xác nhận đã đối chiếu dashboard")
    row.updated_at = meshy.now()
    audit(db, actor, row, "reconciled")
    db.commit()
    return view(row)

@router.get("/admin/meshy/jobs/{job_id}/calibration")
def preview(job_id: UUID, actor: User = Depends(require_user(P.ADMIN_MODELS_3D)), db: Session = Depends(get_db)):
    row = get_job(db, job_id)
    if row.status != "ready":
        raise HTTPException(409, "Model chưa sẵn sàng")
    return meshy.calibration(row, True)

@router.post("/admin/meshy/jobs/{job_id}/calibration")
def placement(job_id: UUID, body: Placement, actor: User = Depends(require_user(P.ADMIN_MODELS_3D)), db: Session = Depends(get_db)):
    row = get_job(db, job_id)
    if row.published:
        raise HTTPException(409, "Gỡ xuất bản trước khi sửa model")
    row.metadata_json = {**row.metadata_json, **body.model_dump()}
    db.commit()
    return {"calibration": meshy.calibration(row, True)}

@router.get("/admin/meshy/jobs/{job_id}/asset")
def private_asset(job_id: UUID, actor: User = Depends(require_user(P.ADMIN_MODELS_3D)), db: Session = Depends(get_db)):
    row = get_job(db, job_id)
    if row.status != "ready" or not meshy.asset(row.id).is_file():
        raise HTTPException(404, "Model chưa tải xong")
    return FileResponse(meshy.asset(row.id), media_type="model/gltf-binary", headers={"Cache-Control": "private, no-store"})

@router.get("/meshy/jobs/{job_id}/asset", dependencies=[Depends(public("only explicitly published AI generated models"))])
def public_asset(job_id: UUID, db: Session = Depends(get_db)):
    row = get_job(db, job_id)
    if not row.published or row.status != "ready" or not meshy.asset(row.id).is_file():
        raise HTTPException(404, "Không tìm thấy model công khai")
    return FileResponse(meshy.asset(row.id), media_type="model/gltf-binary", headers={"Cache-Control": "no-cache"})

@router.post("/admin/meshy/jobs/{job_id}/{action}")
def action(job_id: UUID, action: Literal["previewed", "publish", "unpublish", "resume"], actor: User = Depends(require_user(P.ADMIN_MODELS_3D)), db: Session = Depends(get_db)):
    row = get_job(db, job_id)
    if action == "resume":
        if row.status != "timeout" or not row.task_id:
            raise HTTPException(409, "Không có tác vụ để tiếp tục")
        row.status = "pending"
        row.metadata_json = {**row.metadata_json, "poll_deadline": (meshy.now() + timedelta(hours=2)).isoformat()}
        row.error = None
    elif action == "unpublish":
        row.published = False
    else:
        if row.status != "ready" or not meshy.asset(row.id).is_file():
            raise HTTPException(409, "Model chưa sẵn sàng")
        if action == "previewed":
            row.previewed_at = meshy.now()
        elif not row.previewed_at:
            raise HTTPException(409, "Xem thử model trước khi xuất bản")
        else:
            row.published = True
    row.updated_at = meshy.now()
    audit(db, actor, row, action)
    db.commit()
    return view(row)
