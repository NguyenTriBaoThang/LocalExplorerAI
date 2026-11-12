"""Operator documents (rate sheets, invoices) and versioned supplier rate cards."""
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.llm.provider import LLMProviderError
from app.api.dependencies import get_db, get_llm_provider
from app.api.guards import require_user
from app.api.permissions import P
from app.api.routes.operator import _audit, _org
from app.models.entities import OperatorDocument, OperatorOrg, RateCard, RateCardItem, User
from app.services import operator_documents as docs
from app.services.operator_documents import Extraction, ExtractedLine
from app.services.prompt_service import InvalidStructuredOutput, PromptRunner
from app.services.rate_cards import diff_items, make_code

router = APIRouter(prefix="/api", tags=["operator rate cards"])


def _fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


class UploadBody(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    data_url: str = Field(min_length=20, max_length=14_500_000)
    kind: str = Field(default="rate_sheet", pattern="^(rate_sheet|invoice)$")


class LinesBody(BaseModel):
    supplier: str | None = Field(default=None, max_length=180)
    lines: list[ExtractedLine] = Field(max_length=docs.MAX_ROWS)


class FromDocumentBody(BaseModel):
    supplier: str | None = Field(default=None, max_length=180)
    valid_from: date | None = None
    valid_to: date | None = None


class ApproveBody(BaseModel):
    valid_from: date | None = None
    valid_to: date | None = None


class ItemPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    amount_vnd: int | None = Field(default=None, ge=0, le=10_000_000_000)
    seats: int | None = Field(default=None, ge=1, le=100)
    max_pax: int | None = Field(default=None, ge=1, le=1000)
    conditions: dict | None = None


def doc_payload(doc: OperatorDocument) -> dict:
    return {"id": doc.id, "kind": doc.kind, "filename": doc.filename, "mime": doc.mime, "size_bytes": doc.size_bytes,
            "status": doc.status, "error": doc.error, "extracted": doc.extracted, "created_at": doc.created_at}


def item_payload(i: RateCardItem) -> dict:
    return {"id": i.id, "code": i.code, "label": i.label, "unit": i.unit, "seats": i.seats, "max_pax": i.max_pax,
            "amount_vnd": int(i.amount_vnd), "experience_id": i.experience_id, "conditions": i.conditions or {},
            "confidence": i.confidence, "source_ref": i.source_ref}


def card_payload(card: RateCard, items: bool = False) -> dict:
    out = {"id": card.id, "supplier": card.supplier, "category": card.category, "version": card.version,
           "status": card.status, "valid_from": card.valid_from, "valid_to": card.valid_to,
           "source_document_id": card.source_document_id, "approved_by": card.approved_by,
           "approved_at": card.approved_at, "created_at": card.created_at, "item_count": len(card.items)}
    if items:
        out["items"] = [item_payload(i) for i in card.items]
    return out


def _doc(db: Session, org: OperatorOrg, doc_id: str) -> OperatorDocument:
    doc = db.scalar(select(OperatorDocument).where(OperatorDocument.id == doc_id, OperatorDocument.org_id == org.id))
    if doc is None:
        raise _fail(404, "DOCUMENT_NOT_FOUND", "Không tìm thấy tài liệu.")
    return doc


def _card(db: Session, org: OperatorOrg, card_id: str) -> RateCard:
    card = db.scalar(select(RateCard).where(RateCard.id == card_id, RateCard.org_id == org.id))
    if card is None:
        raise _fail(404, "RATE_CARD_NOT_FOUND", "Không tìm thấy bảng giá.")
    return card


@router.post("/operator/documents", status_code=201)
def upload_document(body: UploadBody, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)), db: Session = Depends(get_db)):
    org = _org(db, user)
    try:
        mime, raw = docs.parse_upload(body.filename, body.data_url)
    except ValueError as error:
        raise _fail(422, "INVALID_DOCUMENT", str(error))
    sha, rel = docs.store(org.id, raw)
    existing = db.scalar(select(OperatorDocument).where(OperatorDocument.org_id == org.id, OperatorDocument.sha256 == sha))
    if existing is not None:  # same bytes uploaded again: reuse, never extract twice
        return doc_payload(existing)
    doc = OperatorDocument(id=str(uuid4()), org_id=org.id, kind=body.kind, filename=body.filename.strip()[:255], mime=mime,
                           size_bytes=len(raw), sha256=sha, storage_path=rel, uploaded_by=user.id)
    db.add(doc)
    _audit(db, user, "operator_document.uploaded", doc.id, {"kind": body.kind, "sha256": sha}, "operator_document")
    db.commit()
    return doc_payload(doc)


@router.get("/operator/documents/{doc_id}")
def get_document(doc_id: str, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)), db: Session = Depends(get_db)):
    return doc_payload(_doc(db, _org(db, user), doc_id))


@router.post("/operator/documents/{doc_id}/extract")
def extract_document(doc_id: str, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)), db: Session = Depends(get_db),
                     provider=Depends(get_llm_provider)):
    doc = _doc(db, _org(db, user), doc_id)
    if doc.status in ("approved", "rejected"):
        raise _fail(409, "DOCUMENT_CLOSED", "Tài liệu đã được duyệt hoặc từ chối.")

    def failed(status: int, code: str, message: str) -> HTTPException:
        doc.status, doc.error = "failed", message
        db.commit()
        return _fail(status, code, message)

    try:
        user_input, attachments = docs.extraction_input(doc.filename, doc.mime, docs.read_stored(doc.storage_path))
    except (ValueError, OSError) as error:
        raise failed(422, "UNREADABLE_DOCUMENT", str(error))
    prompt = "RATE_CARD_EXTRACTOR" if doc.kind == "rate_sheet" else "INVOICE_EXTRACTOR"
    try:
        # ponytail: runs inside the request (worker only runs on Postgres); move to the worker for sheets that time out.
        result = PromptRunner(provider).run(prompt, user_input, Extraction, attachments)
    except LLMProviderError as error:
        hint = " Nhà cung cấp AI có thể không đọc được PDF; hãy gửi ảnh chụp hoặc CSV/XLSX." if doc.mime == "application/pdf" else ""
        raise failed(502, "LLM_PROVIDER_ERROR", f"{error}{hint}")
    except InvalidStructuredOutput as error:
        raise failed(422, "INVALID_MODEL_OUTPUT", str(error))
    doc.extracted = result.model_dump(mode="json")
    doc.status, doc.error = "extracted", None
    _audit(db, user, "operator_document.extracted", doc.id, {"lines": len(result.lines)}, "operator_document")
    db.commit()
    return doc_payload(doc)


@router.patch("/operator/documents/{doc_id}/lines")
def edit_lines(doc_id: str, body: LinesBody, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)), db: Session = Depends(get_db)):
    doc = _doc(db, _org(db, user), doc_id)
    if doc.status != "extracted":
        raise _fail(409, "DOCUMENT_NOT_EDITABLE", "Chỉ sửa được tài liệu đã trích xuất và chưa duyệt.")
    supplier = body.supplier if body.supplier is not None else (doc.extracted or {}).get("supplier")
    doc.extracted = {"supplier": supplier, "lines": [line.model_dump(mode="json") for line in body.lines]}
    _audit(db, user, "operator_document.lines_edited", doc.id, {"lines": len(body.lines)}, "operator_document")
    db.commit()
    return doc_payload(doc)


@router.post("/operator/documents/{doc_id}/reject")
def reject_document(doc_id: str, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)), db: Session = Depends(get_db)):
    doc = _doc(db, _org(db, user), doc_id)
    if doc.status == "approved":
        raise _fail(409, "DOCUMENT_CLOSED", "Tài liệu đã tạo bảng giá, không thể từ chối.")
    doc.status = "rejected"
    _audit(db, user, "operator_document.rejected", doc.id, {}, "operator_document")
    db.commit()
    return doc_payload(doc)


@router.get("/operator/rate-cards")
def list_rate_cards(user: User = Depends(require_user(P.OPERATOR_RATE_CARD)), db: Session = Depends(get_db)):
    org = _org(db, user)
    cards = db.scalars(select(RateCard).where(RateCard.org_id == org.id)
                       .order_by(RateCard.supplier, RateCard.category, RateCard.version.desc())).all()
    return [card_payload(c) for c in cards]


@router.get("/operator/rate-cards/{card_id}")
def get_rate_card(card_id: str, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)), db: Session = Depends(get_db)):
    return card_payload(_card(db, _org(db, user), card_id), items=True)


@router.post("/operator/rate-cards/from-document/{doc_id}", status_code=201)
def card_from_document(doc_id: str, body: FromDocumentBody, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)),
                       db: Session = Depends(get_db)):
    """One draft card per category found in the reviewed lines (a sheet may mix vehicles and surcharges)."""
    org = _org(db, user)
    doc = _doc(db, org, doc_id)
    if doc.status != "extracted" or doc.kind != "rate_sheet":
        raise _fail(409, "DOCUMENT_NOT_READY", "Chỉ tạo bảng giá từ bảng giá đã trích xuất và chưa bị từ chối.")
    supplier = (body.supplier or (doc.extracted or {}).get("supplier") or "").strip()
    lines = [ExtractedLine.model_validate(x) for x in (doc.extracted or {}).get("lines", [])]
    if not supplier:
        raise _fail(422, "SUPPLIER_REQUIRED", "Nhập tên nhà cung cấp.")
    if not lines:
        raise _fail(422, "NO_LINES", "Tài liệu không có dòng giá nào.")
    cards = []
    for category in sorted({line.category for line in lines}):
        last = db.scalar(select(func.max(RateCard.version)).where(
            RateCard.org_id == org.id, RateCard.supplier == supplier, RateCard.category == category))
        card = RateCard(id=str(uuid4()), org_id=org.id, supplier=supplier, category=category, version=(last or 0) + 1,
                        status="draft", valid_from=body.valid_from, valid_to=body.valid_to, source_document_id=doc.id)
        seen: set[str] = set()
        for line in (x for x in lines if x.category == category):
            code = base = make_code(category, line.label, line.unit, line.seats)
            n = 1
            while code in seen:
                n += 1
                code = f"{base}-{n}"
            seen.add(code)
            card.items.append(RateCardItem(id=str(uuid4()), org_id=org.id, code=code, label=line.label, unit=line.unit,
                                           seats=line.seats, max_pax=line.max_pax, amount_vnd=line.amount_vnd,
                                           conditions=line.conditions, confidence=line.confidence, source_ref=line.source_ref))
        db.add(card)
        cards.append(card)
    doc.status = "approved"
    db.flush()
    for card in cards:
        _audit(db, user, "rate_card.drafted", card.id, {"document_id": doc.id, "version": card.version}, "rate_card")
    db.commit()
    return {"cards": [card_payload(c, items=True) for c in cards]}


@router.patch("/operator/rate-cards/{card_id}/items/{item_id}")
def edit_item(card_id: str, item_id: str, body: ItemPatch, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)),
              db: Session = Depends(get_db)):
    card = _card(db, _org(db, user), card_id)
    if card.status != "draft":
        raise _fail(409, "RATE_CARD_IMMUTABLE", "Bảng giá đã duyệt không sửa được; hãy tạo phiên bản mới.")
    item = next((i for i in card.items if i.id == item_id), None)
    if item is None:
        raise _fail(404, "RATE_CARD_ITEM_NOT_FOUND", "Không tìm thấy dòng giá.")
    for key, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(item, key, value)
    db.commit()
    return item_payload(item)


@router.post("/operator/rate-cards/{card_id}/approve")
def approve_card(card_id: str, body: ApproveBody | None = None, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)),
                 db: Session = Depends(get_db)):
    org = _org(db, user)
    card = _card(db, org, card_id)
    if card.status != "draft":
        raise _fail(409, "RATE_CARD_NOT_DRAFT", "Chỉ duyệt được bảng giá nháp.")
    if not card.items:
        raise _fail(422, "NO_ITEMS", "Bảng giá không có dòng nào.")
    previous = db.scalars(select(RateCard).where(
        RateCard.org_id == org.id, RateCard.supplier == card.supplier, RateCard.category == card.category,
        RateCard.status == "active")).all()
    for old in previous:
        old.status = "archived"
    now = datetime.now(timezone.utc)
    card.status, card.approved_by, card.approved_at = "active", user.id, now
    if body and body.valid_from:
        card.valid_from = body.valid_from
    if body and body.valid_to:
        card.valid_to = body.valid_to
    card.valid_from = card.valid_from or now.date()
    _audit(db, user, "rate_card.approved", card.id, {"version": card.version, "archived": [o.id for o in previous]}, "rate_card")
    db.commit()
    return card_payload(card, items=True)


@router.get("/operator/rate-cards/{card_id}/diff/{other_id}")
def diff_cards(card_id: str, other_id: str, user: User = Depends(require_user(P.OPERATOR_RATE_CARD)), db: Session = Depends(get_db)):
    """Changes going from card_id (old) to other_id (new); delta = new - old."""
    org = _org(db, user)
    a, b = _card(db, org, card_id), _card(db, org, other_id)
    if (a.supplier, a.category) != (b.supplier, b.category):
        raise _fail(422, "DIFF_MISMATCH", "Chỉ so sánh được các phiên bản của cùng nhà cung cấp và loại giá.")
    return {"from": card_payload(a), "to": card_payload(b), **diff_items(a.items, b.items)}
