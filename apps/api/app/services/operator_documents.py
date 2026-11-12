"""Operator document intake: upload validation, storage under the app data dir, and the LLM extraction contract."""
import base64
import binascii
import csv
import hashlib
import io
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.xlsx import read_xlsx_rows

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 500  # rows sent to the LLM as text; a longer sheet should be split
MIME_BY_EXT = {
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".pdf": "application/pdf",
}
Category = Literal["vehicle", "guide", "meal", "ticket", "hotel", "surcharge"]
Unit = Literal["per_km", "per_day", "per_trip", "per_pax", "per_room_night", "pct"]


class ExtractedLine(BaseModel):
    category: Category
    label: str = Field(min_length=1, max_length=255)
    unit: Unit
    seats: int | None = Field(default=None, ge=1, le=100)
    max_pax: int | None = Field(default=None, ge=1, le=1000)
    amount_vnd: int = Field(ge=0, le=10_000_000_000)
    conditions: dict = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    source_ref: str | None = Field(default=None, max_length=255)

    @field_validator("conditions", mode="before")
    @classmethod
    def _null_conditions(cls, value):
        return {} if value is None else value


class Extraction(BaseModel):
    supplier: str | None = Field(default=None, max_length=180)
    lines: list[ExtractedLine]


def data_dir() -> Path:
    # APP_DATA_DIR is a mounted volume in docker-compose, so uploads survive container rebuilds.
    return Path(os.environ["APP_DATA_DIR"]) if os.environ.get("APP_DATA_DIR") else Path(__file__).resolve().parents[2] / ".app-data"


def _magic_ok(ext: str, raw: bytes) -> bool:
    if ext == ".csv":
        return b"\0" not in raw[:4096]
    return {
        ".xlsx": raw.startswith(b"PK\x03\x04"),
        ".png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": raw.startswith(b"\xff\xd8\xff"), ".jpeg": raw.startswith(b"\xff\xd8\xff"),
        ".webp": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP",
        ".pdf": raw.startswith(b"%PDF-"),
    }[ext]


def parse_upload(filename: str, data_url: str) -> tuple[str, bytes]:
    """(mime, bytes) for an allowed file. The type comes from the extension, then the content must match it."""
    ext = Path(filename).suffix.lower()
    if ext not in MIME_BY_EXT:
        raise ValueError("Chỉ hỗ trợ CSV, XLSX, PNG, JPEG, WebP hoặc PDF.")
    header, _, encoded = data_url.partition(",")
    if not header.startswith("data:") or not header.endswith(";base64") or len(encoded) > MAX_BYTES * 4 // 3 + 8:
        raise ValueError("Tệp phải là data URL base64, tối đa 10 MB.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Tệp không hợp lệ.")
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Tệp rỗng hoặc vượt quá 10 MB.")
    if not _magic_ok(ext, raw):
        raise ValueError("Nội dung tệp không khớp với phần mở rộng.")
    return MIME_BY_EXT[ext], raw


def store(org_id: str, raw: bytes) -> tuple[str, str]:
    """Write content-addressed bytes; returns (sha256, path relative to the data dir)."""
    sha = hashlib.sha256(raw).hexdigest()
    rel = f"operator_docs/{org_id}/{sha}"
    path = data_dir() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(raw)
    return sha, rel


def read_stored(rel: str) -> bytes:
    return (data_dir() / rel).read_bytes()


def extraction_input(filename: str, mime: str, raw: bytes) -> tuple[dict, list[tuple[str, bytes]]]:
    """Spreadsheets go to the LLM as text rows; images and PDFs as attachments."""
    if mime == "text/csv":
        text = raw.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = [row for row in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in row)]
    elif mime.endswith("spreadsheetml.sheet"):
        try:
            rows = [["" if c is None else c for c in row] for row in read_xlsx_rows(io.BytesIO(raw))]
        except Exception as error:  # zip/xml damage of any kind is the same answer for the user
            raise ValueError("Không đọc được tệp XLSX.") from error
    else:
        # ponytail: PDFs are sent as-is and the provider may reject them; pypdf text extraction is the upgrade path.
        return {"filename": filename}, [(mime, raw)]
    if len(rows) > MAX_ROWS:
        raise ValueError(f"Bảng tính có hơn {MAX_ROWS} dòng; hãy tách nhỏ tệp.")
    return {"filename": filename, "rows": rows}, []
