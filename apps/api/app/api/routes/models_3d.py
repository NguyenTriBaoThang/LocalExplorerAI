"""3D landmark models: serve calibration (vị trí / góc xoay / tỉ lệ) and let admins persist it."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import require_roles
from app.models.entities import User

router = APIRouter(prefix="/models-3d", tags=["3D Models & Landmarks"])

# Repo root: .../apps/api/app/api/routes -> 5 levels up to repo root
_THIS_PATH = Path(__file__).resolve()
REPO_ROOT = _THIS_PATH.parents[5] if len(_THIS_PATH.parents) > 5 else _THIS_PATH.parents[4]
CALIBRATION_FILE = REPO_ROOT / "models_3d" / "calibration.json"
MODEL_ID_PATTERN = re.compile(r"^[a-z0-9_-]{1,64}$")

# `scale` = chiều cao thực tế của công trình (mét). Mô hình được chuẩn hoá về cao 1 đơn vị ở frontend.
DEFAULT_MODELS: Dict[str, Dict[str, Any]] = {
    "nhathoducba": {
        "model_name": "nhathoducba",
        "display_name": "Nhà thờ Đức Bà Sài Gòn",
        "file_url": "/models_3d/NhaThoDucBa2_cathedral_textured_1004080927_texture.glb",
        "latitude": 10.779740,
        "longitude": 106.699040,
        "altitude": 0.0,
        "heading": 312.5,
        "pitch": 0.0,
        "roll": 0.0,
        "scale": 77.5,
        "poi_id": "exp-sai-gon-nha-tho-uc-ba-sai-gon",
        "description": "Biểu tượng kiến trúc Công giáo La Mã cổ kính hơn 140 năm tại Công xã Paris, Quận 1.",
        "updated_at": None,
    }
}


def _resolve_read_path() -> Path:
    if CALIBRATION_FILE.exists():
        return CALIBRATION_FILE
    fallback = REPO_ROOT / "apps" / "models_3d" / "calibration.json"
    if fallback.exists():
        return fallback
    return CALIBRATION_FILE


def _read_calibrations() -> Dict[str, Any]:
    stored: Dict[str, Any] = {}
    target = _resolve_read_path()
    if target.exists():
        try:
            stored = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stored = {}
    merged = {key: {**value} for key, value in DEFAULT_MODELS.items()}
    for key, value in stored.items():
        if isinstance(value, dict):
            merged[key] = {**merged.get(key, {}), **value}
    return merged


def _save_calibrations(data: Dict[str, Any]) -> None:
    CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CALIBRATION_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CALIBRATION_FILE)


def _get_known_model(model_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not MODEL_ID_PATTERN.match(model_id) or model_id not in data:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu hình mô hình 3D này.")
    return data[model_id]


class CalibrationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    latitude: float = Field(..., ge=-90, le=90, description="Vĩ độ WGS84")
    longitude: float = Field(..., ge=-180, le=180, description="Kinh độ WGS84")
    altitude: float = Field(default=0.0, ge=-50, le=200, description="Độ cao so với mặt đất (mét)")
    heading: float = Field(default=0.0, ge=0, lt=360, description="Hướng mặt tiền, độ theo chiều kim đồng hồ từ hướng Bắc")
    pitch: float = Field(default=0.0, ge=-90, le=90)
    roll: float = Field(default=0.0, ge=-90, le=90)
    scale: float = Field(default=58.0, gt=0.5, le=1000, description="Chiều cao thực tế (mét)")


@router.get("/calibration")
def get_all_calibrations():
    """Lấy thông số hiệu chỉnh của tất cả mô hình 3D."""
    return _read_calibrations()


@router.get("/calibration/{model_id}")
def get_model_calibration(model_id: str):
    """Lấy thông số hiệu chỉnh của một mô hình (ví dụ: nhathoducba)."""
    return _get_known_model(model_id, _read_calibrations())


@router.post("/calibration/{model_id}")
def save_model_calibration(
    model_id: str,
    payload: CalibrationPayload,
    actor: User = Depends(require_roles("admin")),
):
    """Admin lưu vị trí, góc xoay và tỉ lệ đã căn chỉnh của mô hình 3D."""
    data = _read_calibrations()
    item = {
        **_get_known_model(model_id, data),
        **payload.model_dump(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": actor.id,
    }
    data[model_id] = item
    _save_calibrations(data)
    return {"ok": True, "message": "Đã lưu tọa độ hiệu chỉnh thành công!", "calibration": item}
