"""3D landmark models: serve calibration (vị trí / góc xoay / tỉ lệ) and let admins persist it."""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import require_roles
from app.models.entities import User

router = APIRouter(prefix="/models-3d", tags=["3D Models & Landmarks"])

# Repo root: .../apps/api/app/api/routes -> 5 levels up to repo root
_THIS_PATH = Path(__file__).resolve()
REPO_ROOT = _THIS_PATH.parents[5] if len(_THIS_PATH.parents) > 5 else _THIS_PATH.parents[4]
CALIBRATION_FILE = REPO_ROOT / "models_3d" / "calibration.json"
MODEL_PACKS_DIR = REPO_ROOT / "models_3d"
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


DEFAULT_MODELS.update({
    "dinhdoclap": {
        "model_name": "dinhdoclap",
        "display_name": "Dinh Độc Lập",
        "file_url": "/models_3d/Independence_Palace.glb",
        "latitude": 10.777052,
        "longitude": 106.695428,
        "altitude": 0.0,
        "heading": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
        "scale": 26.0,
        "poi_id": "dinhdoclap",
        "description": "Dinh Độc Lập, di tích lịch sử tại Quận 1.",
        "updated_at": None,
    },
    "chobenthanh": {
        "model_name": "chobenthanh",
        "display_name": "Chợ Bến Thành",
        "file_url": "/models_3d/Ben_Thanh_Market.glb",
        "latitude": 10.7725,
        "longitude": 106.6980,
        "altitude": 0.0,
        "heading": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
        "scale": 28.0,
        "poi_id": "chobenthanh",
        "description": "Chợ Bến Thành, công trình biểu tượng tại Quận 1.",
        "updated_at": None,
    },
    "nhahatthanhpho": {
        "model_name": "nhahatthanhpho",
        "display_name": "Nhà hát Thành phố",
        "file_url": "/models_3d/Saigon_Opera_House.glb",
        "latitude": 10.7769,
        "longitude": 106.7030,
        "altitude": 0.0,
        "heading": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
        "scale": 24.0,
        "poi_id": "nhahatthanhpho",
        "description": "Nhà hát Thành phố Hồ Chí Minh, công trình kiến trúc tại Quận 1.",
        "updated_at": None,
    },
})

DEFAULT_MODELS.update({
    "bitexco": {
        "model_name": "bitexco",
        "display_name": "Bitexco Financial Tower",
        "file_url": "/models_3d/Bitexco_Tower.glb",
        "latitude": 10.7717,
        "longitude": 106.7043,
        "altitude": 0.0,
        "heading": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
        "scale": 262.0,
        "poi_id": "bitexco",
        "description": "Bitexco Financial Tower, công trình biểu tượng tại Quận 1.",
        "updated_at": None,
    },
    "landmark81": {
        "model_name": "landmark81",
        "display_name": "Landmark 81",
        "file_url": "/models_3d/Landmark_81.glb",
        "latitude": 10.7950,
        "longitude": 106.7218,
        "altitude": 0.0,
        "heading": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
        "scale": 461.0,
        "poi_id": "landmark81",
        "description": "Landmark 81, tòa nhà cao nhất TP. Hồ Chí Minh.",
        "updated_at": None,
    },
})
DEFAULT_MODELS["hoian"] = {
    "model_name": "hoian",
    "display_name": "Phố cổ Hội An - Chùa Cầu",
    "file_url": "/models_3d/HoiAn_ChuaCau_web.glb",
    "latitude": 15.8779,
    "longitude": 108.3264,
    "altitude": 0.0,
    "heading": 0.0,
    "pitch": 0.0,
    "roll": 0.0,
    "scale": 10.0,
    "poi_id": "hoi-an-chua-cau",
    "description": "Mô hình 3D khu phố cổ Hội An, đặt gần Chùa Cầu.",
    "updated_at": None,
}
DEFAULT_MODELS["vungtauchrist"] = {
    "model_name": "vungtauchrist",
    "display_name": "Tượng Chúa Kitô Vua Vũng Tàu",
    "file_url": "/models_3d/VungTauChristDiorama3_web.glb",
    "latitude": 10.3264,
    "longitude": 107.0845,
    "altitude": 0.0,
    "heading": 0.0,
    "pitch": 0.0,
    "roll": 0.0,
    "scale": 42.0,
    "poi_id": "vungtau-christ",
    "description": "Mô hình 3D Tượng Chúa Kitô Vua trên Núi Nhỏ, Vũng Tàu.",
    "updated_at": None,
}


def _resolve_read_path() -> Path:
    if CALIBRATION_FILE.exists():
        return CALIBRATION_FILE
    fallback = REPO_ROOT / "apps" / "models_3d" / "calibration.json"
    if fallback.exists():
        return fallback
    return CALIBRATION_FILE


def _folder_model_id(value: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", ascii_name.strip()).strip("-_").lower()
    return slug[:64]


def _discover_folder_models() -> Dict[str, Dict[str, Any]]:
    """Discover GLB model packs under models_3d/<folder>/ without code registration."""
    discovered: Dict[str, Dict[str, Any]] = {}
    if not MODEL_PACKS_DIR.is_dir():
        return discovered

    for folder in sorted(MODEL_PACKS_DIR.iterdir(), key=lambda item: item.name.casefold()):
        if not folder.is_dir() or folder.name.startswith((".", "_")):
            continue
        model_id = _folder_model_id(folder.name)
        if not model_id or not MODEL_ID_PATTERN.fullmatch(model_id):
            continue
        glb_files = sorted(
            (path for path in folder.rglob("*") if path.is_file() and path.suffix.casefold() == ".glb"),
            key=lambda item: item.as_posix().casefold(),
        )
        if not glb_files:
            continue

        for glb in glb_files:
            current_id = model_id if len(glb_files) == 1 else _folder_model_id(f"{folder.name}-{glb.stem}")
            if not current_id or not MODEL_ID_PATTERN.fullmatch(current_id):
                continue
            if current_id in DEFAULT_MODELS or current_id in discovered:
                continue

            metadata: Dict[str, Any] = {}
            metadata_path = (folder / "model.json") if len(glb_files) == 1 else glb.with_suffix(".json")
            if metadata_path.is_file():
                try:
                    value = json.loads(metadata_path.read_text(encoding="utf-8"))
                    if isinstance(value, dict):
                        metadata = value
                except (OSError, json.JSONDecodeError):
                    pass

            file_url = "/models_3d/_generated/" + quote(current_id, safe="-_.~") + "/model.glb"
            fallback_name = folder.name if len(glb_files) == 1 else glb.stem
            display_name = str(metadata.get("display_name") or re.sub(r"[_-]+", " ", fallback_name)).strip()

            def number(key: str, fallback: float, minimum: float, maximum: float) -> float:
                try:
                    result = float(metadata.get(key, fallback))
                except (TypeError, ValueError):
                    return fallback
                return result if minimum <= result <= maximum else fallback

            discovered[current_id] = {
                "model_name": current_id,
                "display_name": display_name or fallback_name,
                "file_url": file_url,
                # GPS cannot be derived from a GLB. These defaults make the model visible;
                # the map calibrator can place it correctly or a JSON sidecar can set the point.
                "latitude": number("latitude", 10.779785, -90, 90),
                "longitude": number("longitude", 106.699018, -180, 180),
                "altitude": number("altitude", 0, -50, 200),
                "heading": number("heading", 0, 0, 359.999),
                "pitch": number("pitch", 0, -90, 90),
                "roll": number("roll", 0, -90, 90),
                "scale": number("scale", 20, 0.500001, 1000),
                "poi_id": metadata.get("poi_id"),
                "description": str(metadata.get("description") or "Model tự phát hiện từ thư mục models_3d. Hãy căn vị trí trên Map3D."),
                "updated_at": None,
            }
    return discovered


def _read_calibrations() -> Dict[str, Any]:
    stored: Dict[str, Any] = {}
    target = _resolve_read_path()
    if target.exists():
        try:
            stored = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stored = {}
    merged = {key: {**value} for key, value in DEFAULT_MODELS.items()}
    merged.update(_discover_folder_models())
    for key, value in stored.items():
        if isinstance(value, dict) and key in merged:
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
