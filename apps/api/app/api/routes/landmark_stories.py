"""Public published stories and permission-checked editorial workflow."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.guards import public, require_user
from app.api.permissions import P
from app.api.routes.models_3d import _get_known_model, _read_calibrations
from app.db.session import get_db
from app.models.entities import AuditLog, LandmarkStory, User
from app.schemas.landmark_story import LandmarkStoryPayload, StorySave, StoryAction

router = APIRouter(prefix="/api", tags=["landmark stories"])


def known(model_id, db):
    return _get_known_model(model_id, _read_calibrations(db))


def view(row, model_id):
    return {"model_id": model_id, "revision": row.revision if row else 0,
            "workflow": row.workflow if row else "draft",
            "content": row.draft if row else LandmarkStoryPayload().model_dump(mode="json"),
            "published": row.published if row else None,
            "updated_at": row.updated_at if row else None,
            "published_at": row.published_at if row else None}


def locked(db, model_id, revision):
    row = db.scalar(select(LandmarkStory).where(LandmarkStory.model_id == model_id).with_for_update())
    if (row.revision if row else 0) != revision:
        raise HTTPException(409, detail={"code": "STORY_CHANGED", "message": "Nội dung đã đổi. Hãy tải lại trước khi lưu."})
    return row


def audit(db, actor, model_id, action, revision):
    db.add(AuditLog(id=str(uuid4()), actor_id=actor.id, action=f"landmark_story.{action}",
                    target_type="landmark_story", target_id=model_id,
                    details={"revision": revision}, created_at=datetime.now(timezone.utc)))


@router.get("/landmark-stories/{model_id}", dependencies=[Depends(public("published heritage stories"))])
def get_story(model_id: str, db: Session = Depends(get_db)):
    model = known(model_id, db)
    row = db.get(LandmarkStory, model_id)
    return {"model_id": model_id, "display_name": model["display_name"],
            "content": row.published if row else None,
            "published_at": row.published_at if row and row.published else None}


@router.get("/admin/landmark-stories")
def list_stories(actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    models = _read_calibrations(db)
    rows = {row.model_id: row for row in db.scalars(select(LandmarkStory))}
    return [{"model_id": key, "display_name": model["display_name"],
             "workflow": rows[key].workflow if key in rows else "draft",
             "is_published": bool(key in rows and rows[key].published)} for key, model in models.items()]


@router.get("/admin/landmark-stories/{model_id}")
def get_draft(model_id: str, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    known(model_id, db)
    return view(db.get(LandmarkStory, model_id), model_id)


@router.put("/admin/landmark-stories/{model_id}")
def save_story(model_id: str, payload: StorySave, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    known(model_id, db)
    row = locked(db, model_id, payload.revision)
    if row is None:
        row = LandmarkStory(model_id=model_id, revision=0)
        db.add(row)
    row.draft = payload.content.model_dump(mode="json")
    row.workflow = "draft"
    row.revision += 1
    row.updated_at = datetime.now(timezone.utc)
    audit(db, actor, model_id, "saved", row.revision)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail="Nội dung vừa được tạo ở phiên khác. Hãy tải lại.")
    return view(row, model_id)


@router.post("/admin/landmark-stories/{model_id}/{action}")
def change_status(model_id: str, action: str, payload: StoryAction,
                  actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    known(model_id, db)
    if action not in {"submit", "publish", "unpublish"}:
        raise HTTPException(404, detail="Unknown editorial action")
    row = locked(db, model_id, payload.revision)
    if row is None:
        raise HTTPException(404, detail="Hãy lưu bản nháp trước")
    if action in {"submit", "publish"}:
        content = LandmarkStoryPayload.model_validate(row.draft)
        if content.overview.status != "sourced":
            raise HTTPException(422, detail="Tổng quan cần nội dung có nguồn trước khi gửi duyệt")
        for item in content.timeline:
            if item.status != "sourced":
                raise HTTPException(422, detail="Các mốc lịch sử phải có nguồn trước khi gửi duyệt")
    if action == "publish":
        if row.workflow != "review":
            raise HTTPException(409, detail="Cần gửi duyệt bản nháp trước khi xuất bản")
        row.published = content.model_dump(mode="json")
        row.published_at = datetime.now(timezone.utc)
        row.workflow = "published"
    elif action == "submit":
        row.workflow = "review"
    else:
        row.published = None
        row.published_at = None
        row.workflow = "draft"
    row.revision += 1
    row.updated_at = datetime.now(timezone.utc)
    audit(db, actor, model_id, action, row.revision)
    db.commit()
    return view(row, model_id)
