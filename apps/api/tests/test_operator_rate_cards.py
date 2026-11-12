import base64
import io
import zipfile
from datetime import date

import pytest

from app.api.dependencies import get_llm_provider
from app.adapters.llm.provider import LLMProviderError
from app.models.entities import OperatorOrg
from app.services.quote.cost_engine import QuoteRequestLite, compute_cost
from app.services.rate_cards import active_rate_items
from tests.helpers import bearer_for, make_user


def make_xlsx(rows) -> bytes:
    """Smallest valid workbook the stdlib reader understands (inline strings)."""
    cells = "".join(
        f'<row r="{r}">' + "".join(
            f'<c r="{chr(65 + c)}{r}" t="inlineStr"><is><t>{v}</t></is></c>' for c, v in enumerate(row)) + "</row>"
        for r, row in enumerate(rows, start=1))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Gia" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{cells}</sheetData></worksheet>')
    return buf.getvalue()


def data_url(raw: bytes, mime="application/octet-stream") -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


LINES = [
    {"category": "vehicle", "label": "Xe 16 chỗ", "unit": "per_day", "seats": 16, "amount_vnd": 1_800_000, "conditions": {}, "confidence": 0.95, "source_ref": "dòng 2"},
    {"category": "vehicle", "label": "Xe 16 chỗ km", "unit": "per_km", "seats": 16, "amount_vnd": 9_000, "conditions": {}, "confidence": 0.5, "source_ref": "dòng 3"},
    {"category": "surcharge", "label": "Phụ thu lễ", "unit": "pct", "amount_vnd": 25, "conditions": {"holiday": True}, "confidence": 0.9, "source_ref": "dòng 4"},
]


class FakeLLM:
    model_name = "fake"

    def __init__(self, lines=LINES, supplier="Nhà xe An Phú"):
        self.calls, self.lines, self.supplier = [], lines, supplier

    def generate(self, system_prompt, user_input, schema, attachments=()):
        self.calls.append((system_prompt, user_input, list(attachments)))
        return {"supplier": self.supplier, "lines": self.lines}


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))


@pytest.fixture
def op(db_session):
    org = OperatorOrg(name="Org A", slug="org-a", settings={})
    db_session.add(org)
    db_session.commit()
    return make_user(db_session, "operator", operator_org_id=org.id)


@pytest.fixture
def llm(client):
    fake = FakeLLM()
    client.app.dependency_overrides[get_llm_provider] = lambda: fake
    return fake


def upload(client, user, name="gia.csv", raw=b"a,b\n1,2\n", **kw):
    return client.post("/api/operator/documents", json={"filename": name, "data_url": data_url(raw), **kw}, headers=bearer_for(user))


def to_card(client, user, doc_id):
    r = client.post(f"/api/operator/rate-cards/from-document/{doc_id}", json={}, headers=bearer_for(user))
    assert r.status_code == 201, r.text
    return {c["category"]: c for c in r.json()["cards"]}


def extracted_doc(client, user, raw=b"a,b\n1,2\n"):
    doc = upload(client, user, raw=raw).json()
    assert client.post(f"/api/operator/documents/{doc['id']}/extract", headers=bearer_for(user)).status_code == 200
    return doc["id"]


def test_upload_validation(client, op):
    assert upload(client, op, "gia.exe").status_code == 422
    assert upload(client, op, "gia.pdf", b"not a pdf").status_code == 422          # content must match the extension
    assert upload(client, op, "gia.png", b"\x89PNG\r\n\x1a\nxx").status_code == 201
    big = client.post("/api/operator/documents", json={"filename": "x.csv", "data_url": data_url(b"a" * (10 * 1024 * 1024 + 1))}, headers=bearer_for(op))
    assert big.status_code == 422
    bad = client.post("/api/operator/documents", json={"filename": "x.csv", "data_url": "data:text/csv;base64,@@@@@@@@@@@@@@@@@@@@"}, headers=bearer_for(op))
    assert bad.status_code == 422


def test_upload_dedupes_by_hash_per_org(client, db_session, op):
    a = upload(client, op).json()
    assert upload(client, op).json()["id"] == a["id"]
    other = make_user(db_session, "operator", operator_org_id=_new_org(db_session, "Org B").id)
    assert upload(client, other).json()["id"] != a["id"]


def _new_org(db, name):
    org = OperatorOrg(name=name, slug=name.lower().replace(" ", "-"), settings={})
    db.add(org)
    db.commit()
    return org


def test_csv_extraction_sends_rows_as_text(client, op, llm):
    doc_id = extracted_doc(client, op, b"Loai xe;Gia\nXe 16 cho;1.800.000\n")
    system, user_input, attachments = llm.calls[0]
    assert user_input["rows"] == [["Loai xe", "Gia"], ["Xe 16 cho", "1.800.000"]] and attachments == []
    got = client.get(f"/api/operator/documents/{doc_id}", headers=bearer_for(op)).json()
    assert got["status"] == "extracted" and len(got["extracted"]["lines"]) == 3 and got["extracted"]["supplier"] == "Nhà xe An Phú"


def test_xlsx_extraction_and_xlsx_helper(client, op, llm):
    raw = make_xlsx([["Loai xe", "Gia"], ["Xe 16 cho", "1.800.000"]])
    extracted_doc(client, op, raw=b"x")  # unrelated csv first
    doc = upload(client, op, "gia.xlsx", raw).json()
    assert client.post(f"/api/operator/documents/{doc['id']}/extract", headers=bearer_for(op)).status_code == 200
    assert llm.calls[-1][1]["rows"][1] == ["Xe 16 cho", "1.800.000"]


def test_image_goes_as_attachment(client, op, llm):
    doc = upload(client, op, "gia.png", b"\x89PNG\r\n\x1a\nxx").json()
    assert client.post(f"/api/operator/documents/{doc['id']}/extract", headers=bearer_for(op)).status_code == 200
    assert llm.calls[0][2] == [("image/png", b"\x89PNG\r\n\x1a\nxx")]


def test_provider_failure_marks_failed_and_bad_output_is_422(client, op):
    class Broken:
        model_name = "b"
        def generate(self, *a, **k):
            raise LLMProviderError("Structured generation failed (HTTP 400).")
    client.app.dependency_overrides[get_llm_provider] = lambda: Broken()
    doc = upload(client, op, "gia.pdf", b"%PDF-1.4 x").json()
    r = client.post(f"/api/operator/documents/{doc['id']}/extract", headers=bearer_for(op))
    assert r.status_code == 502 and "PDF" in r.json()["error"]["message"]
    assert client.get(f"/api/operator/documents/{doc['id']}", headers=bearer_for(op)).json()["status"] == "failed"
    client.app.dependency_overrides[get_llm_provider] = lambda: FakeLLM(lines=[{"category": "nope"}])
    csv_doc = upload(client, op).json()
    assert client.post(f"/api/operator/documents/{csv_doc['id']}/extract", headers=bearer_for(op)).status_code == 422


def test_edit_lines_then_rejected_doc_never_becomes_card(client, op, llm):
    doc_id = extracted_doc(client, op)
    edited = [{**LINES[0], "amount_vnd": 1_700_000, "confidence": 1}]
    r = client.patch(f"/api/operator/documents/{doc_id}/lines", json={"lines": edited}, headers=bearer_for(op))
    assert r.status_code == 200 and r.json()["extracted"]["lines"][0]["amount_vnd"] == 1_700_000
    assert client.post(f"/api/operator/documents/{doc_id}/reject", headers=bearer_for(op)).json()["status"] == "rejected"
    assert client.post(f"/api/operator/rate-cards/from-document/{doc_id}", json={}, headers=bearer_for(op)).status_code == 409
    assert client.post(f"/api/operator/documents/{doc_id}/extract", headers=bearer_for(op)).status_code == 409
    assert client.patch(f"/api/operator/documents/{doc_id}/lines", json={"lines": edited}, headers=bearer_for(op)).status_code == 409
    fresh = upload(client, op, raw=b"other\n").json()  # not extracted yet
    assert client.post(f"/api/operator/rate-cards/from-document/{fresh['id']}", json={}, headers=bearer_for(op)).status_code == 409


def test_approve_archives_previous_and_items_become_immutable(client, op, llm):
    cards = to_card(client, op, extracted_doc(client, op))
    veh = cards["vehicle"]
    assert veh["version"] == 1 and veh["status"] == "draft" and {i["code"] for i in veh["items"]} == {"vehicle-16s-per_day", "vehicle-16s-per_km"}
    item = veh["items"][0]
    assert client.patch(f"/api/operator/rate-cards/{veh['id']}/items/{item['id']}", json={"amount_vnd": 1_750_000}, headers=bearer_for(op)).status_code == 200
    ok = client.post(f"/api/operator/rate-cards/{veh['id']}/approve", headers=bearer_for(op))
    assert ok.status_code == 200 and ok.json()["status"] == "active" and ok.json()["valid_from"]
    assert client.post(f"/api/operator/rate-cards/{veh['id']}/approve", headers=bearer_for(op)).status_code == 409
    assert client.patch(f"/api/operator/rate-cards/{veh['id']}/items/{item['id']}", json={"amount_vnd": 1}, headers=bearer_for(op)).status_code == 409

    llm.lines = [{**LINES[0], "amount_vnd": 2_000_000}, LINES[1]]
    v2 = to_card(client, op, extracted_doc(client, op, b"v2\n"))["vehicle"]
    assert v2["version"] == 2
    client.post(f"/api/operator/rate-cards/{v2['id']}/approve", headers=bearer_for(op))
    listed = {c["id"]: c for c in client.get("/api/operator/rate-cards", headers=bearer_for(op)).json()}
    assert listed[veh["id"]]["status"] == "archived" and listed[v2["id"]]["status"] == "active"


def test_diff_between_versions(client, op, llm):
    v1 = to_card(client, op, extracted_doc(client, op))["vehicle"]
    llm.lines = [{**LINES[0], "amount_vnd": 2_000_000}, {**LINES[2], "category": "vehicle", "label": "Xe 29", "unit": "per_day", "seats": 29, "amount_vnd": 2_500_000}]
    v2 = to_card(client, op, extracted_doc(client, op, b"v2\n"))["vehicle"]
    d = client.get(f"/api/operator/rate-cards/{v1['id']}/diff/{v2['id']}", headers=bearer_for(op)).json()
    assert d["changed"] == [{"code": "vehicle-16s-per_day", "label": "Xe 16 chỗ", "old_vnd": 1_800_000, "new_vnd": 2_000_000, "delta_vnd": 200_000, "delta_pct": 11.1}]
    assert [x["code"] for x in d["added"]] == ["vehicle-29s-per_day"] and [x["code"] for x in d["removed"]] == ["vehicle-16s-per_km"]
    llm.lines = LINES
    sur = to_card(client, op, extracted_doc(client, op, b"v3\n"))["surcharge"]
    assert client.get(f"/api/operator/rate-cards/{v1['id']}/diff/{sur['id']}", headers=bearer_for(op)).status_code == 422


def test_tenancy_isolation(client, db_session, op, llm):
    doc_id = extracted_doc(client, op)
    card = to_card(client, op, doc_id)["vehicle"]
    other = make_user(db_session, "operator", operator_org_id=_new_org(db_session, "Org B").id)
    h = bearer_for(other)
    assert client.get(f"/api/operator/documents/{doc_id}", headers=h).status_code == 404
    assert client.post(f"/api/operator/documents/{doc_id}/reject", headers=h).status_code == 404
    assert client.get(f"/api/operator/rate-cards/{card['id']}", headers=h).status_code == 404
    assert client.post(f"/api/operator/rate-cards/{card['id']}/approve", headers=h).status_code == 404
    assert client.get("/api/operator/rate-cards", headers=h).json() == []
    assert client.get(f"/api/operator/rate-cards/{card['id']}/diff/{card['id']}", headers=h).status_code == 404


def test_other_roles_forbidden(client, db_session):
    for role in ("traveler", "provider"):
        assert client.get("/api/operator/rate-cards", headers=bearer_for(make_user(db_session, role))).status_code == 403


def test_active_rate_items_feed_the_cost_engine(client, db_session, op):
    from app.models.entities import RateCard, RateCardItem

    def card(category, supplier, items, status="active"):
        c = RateCard(org_id=op.operator_org_id, supplier=supplier, category=category, version=1, status=status, valid_from=date(2026, 1, 1))
        for code, unit, amount, kw in items:
            c.items.append(RateCardItem(org_id=op.operator_org_id, code=code, label=code, unit=unit, amount_vnd=amount, conditions=kw.pop("conditions", {}), **kw))
        db_session.add(c)

    card("vehicle", "Nhà xe A", [("v29d", "per_day", 2_300_000, {"seats": 29}), ("v29k", "per_km", 9_000, {"seats": 29}),
                                 ("v16d", "per_day", 1_700_000, {"seats": 16}), ("v16k", "per_km", 8_000, {"seats": 16})])
    card("guide", "HDV", [("g", "per_day", 1_000_000, {})])
    card("meal", "Nhà hàng", [("m", "per_pax", 150_000, {})])
    card("ticket", "Vé", [("ticket-cu-chi", "per_pax", 125_000, {})])
    card("hotel", "KS", [("h", "per_room_night", 700_000, {})])
    card("surcharge", "PT", [("we", "pct", 10, {"conditions": {"weekdays": ["sat", "sun"]}})])
    card("guide", "Cũ", [("g-old", "per_day", 1, {})], status="archived")
    db_session.commit()
    items = active_rate_items(db_session, op.operator_org_id, date(2026, 11, 14))
    assert len(items) == 9 and {i.supplier for i in items if i.category == "vehicle"} == {"Nhà xe A"}
    assert active_rate_items(db_session, op.operator_org_id, date(2025, 1, 1)) == []  # not valid yet
    itin = {"days": [{"legs": [{"distance_km": 60}], "stops": [{"ticket_code": "ticket-cu-chi"}]}, {"legs": [{"distance_km": 60}], "stops": []}]}
    b = compute_cost(itin, QuoteRequestLite(32, 2, meals=3), items, date(2026, 11, 14))  # a Saturday
    assert b.total > 0 and any(l.surcharge_vnd for l in b.lines) and {l.category for l in b.lines} >= {"vehicle", "guide", "meal", "ticket", "hotel"}


def test_provider_renders_attachments_as_image_url_parts_and_default_is_unchanged(monkeypatch):
    import json

    import httpx

    from app.adapters.llm.provider import OpenAICompatibleLLMProvider

    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    p = OpenAICompatibleLLMProvider("k", "m", "http://x")
    p.generate("sys", {"a": 1}, {})
    p.generate("sys", {"a": 1}, {}, attachments=[("image/png", b"\x01")])
    assert bodies[0]["messages"][1]["content"] == '{"a": 1}'
    parts = bodies[1]["messages"][1]["content"]
    assert parts[0] == {"type": "text", "text": '{"a": 1}'}
    assert parts[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AQ=="}}


def test_demo_seed_is_idempotent_and_prices_a_32_pax_two_day_trip(db_session):
    from scripts.seed_operator_demo import ORG_SLUG, seed

    assert seed(lambda: db_session) == {"org": True, "user": True, "cards": 8, "templates": 6, "history": 0}
    assert seed(lambda: db_session) == {"org": False, "user": False, "cards": 0, "templates": 0, "history": 0}
    org = db_session.query(OperatorOrg).filter_by(slug=ORG_SLUG).one()
    items = active_rate_items(db_session, org.id, date(2026, 12, 5))  # a Saturday
    itin = {"days": [{"legs": [{"distance_km": 70}], "stops": [{"ticket_code": "ticket-dia-dao-cu-chi"}]},
                     {"legs": [{"distance_km": 90}], "stops": [{"ticket_code": "ticket-can-gio"}]}]}
    b = compute_cost(itin, QuoteRequestLite(32, 2, meals=3), items, date(2026, 12, 5))
    assert 8_000_000 < b.total < 60_000_000
    assert [l.label for l in b.lines if l.category == "vehicle"][0].startswith("Xe 45 chỗ")  # 33 seats: one 45-seater beats 29+4
    assert any(l.surcharge_codes == ("surcharge-weekend",) for l in b.lines)
