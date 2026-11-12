from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.entities import CostActual, OperatorDocument, OperatorOrg, Quote
from app.services.quote.reconciliation import match
from tests.helpers import bearer_for, make_user

LINES = [
    {"category": "vehicle", "label": "Xe 45 chỗ (45 seats)", "qty": 1, "unit_vnd": 3_300_000, "amount_vnd": 3_300_000, "surcharge_vnd": 330_000, "total_vnd": 3_630_000, "rate_item_id": None},
    {"category": "vehicle", "label": "Distance 140 km (45 seats)", "qty": 140, "unit_vnd": 15_000, "amount_vnd": 2_100_000, "surcharge_vnd": 0, "total_vnd": 2_100_000, "rate_item_id": None},
    {"category": "guide", "label": "Hướng dẫn viên nội địa", "qty": 2, "unit_vnd": 800_000, "amount_vnd": 1_600_000, "surcharge_vnd": 0, "total_vnd": 1_600_000, "rate_item_id": None},
    {"category": "meal", "label": "Cơm suất (set 6 món)", "qty": 64, "unit_vnd": 120_000, "amount_vnd": 7_680_000, "surcharge_vnd": 0, "total_vnd": 7_680_000, "rate_item_id": None},
    {"category": "ticket", "label": "Vé tham quan Địa đạo Củ Chi", "qty": 32, "unit_vnd": 125_000, "amount_vnd": 4_000_000, "surcharge_vnd": 0, "total_vnd": 4_000_000, "rate_item_id": None},
    {"category": "hotel", "label": "Phòng đôi 3★", "qty": 16, "unit_vnd": 700_000, "amount_vnd": 11_200_000, "surcharge_vnd": 0, "total_vnd": 11_200_000, "rate_item_id": None},
]


def inv(category, label, amount, qty=None):
    return {"category": category, "label": label, "amount_vnd": amount, "unit": "per_trip", "conditions": {} if qty is None else {"qty": qty, "unit_price_vnd": amount // qty}}


INVOICE = [
    inv("vehicle", "Thuê xe 45 chỗ", 3_300_000, 1),               # billed without the weekend surcharge: delta == -surcharge
    inv("vehicle", "Distance 140 km (45 seats)", 2_100_000, 140),  # exact
    inv("guide", "Hướng dẫn viên", 2_400_000, 3),                 # one more guide: qty differs
    inv("meal", "Cơm suất 6 món", 8_320_000, 64),                 # same qty, 130k each: price change
    inv("ticket", "Vé Địa đạo Củ Chi", 4_000_000, 32),            # exact
    inv("ticket", "Phí gửi xe", 450_000, 1),                      # not quoted
]


def by_label(rows):
    return {r["label"]: r for r in rows}


def test_match_assigns_reason_for_each_case():
    rows = by_label(match(LINES, INVOICE))
    assert len(rows) == 7
    r = rows["Xe 45 chỗ (45 seats)"]
    assert (r["reason"], r["variance_vnd"], r["matched_cost_line"]) == ("surcharge", -330_000, 0)
    assert rows["Distance 140 km (45 seats)"]["reason"] is None and rows["Distance 140 km (45 seats)"]["variance_vnd"] == 0
    assert (rows["Hướng dẫn viên nội địa"]["reason"], rows["Hướng dẫn viên nội địa"]["variance_vnd"]) == ("pax_change", 800_000)
    assert (rows["Cơm suất (set 6 món)"]["reason"], rows["Cơm suất (set 6 món)"]["variance_vnd"]) == ("price_change", 640_000)
    assert rows["Vé tham quan Địa đạo Củ Chi"]["reason"] is None
    r = rows["Phí gửi xe"]
    assert (r["reason"], r["quoted_vnd"], r["actual_vnd"], r["matched_cost_line"]) == ("unplanned", 0, 450_000, None)
    r = rows["Phòng đôi 3★"]
    assert (r["reason"], r["actual_vnd"], r["variance_vnd"]) == ("not_used", 0, -11_200_000)


def test_one_to_one_leftover_pairs_despite_a_different_name_but_not_across_categories():
    rows = match(LINES[:1], [inv("vehicle", "Chuyến Sài Gòn - Củ Chi", 4_000_000, 1), inv("guide", "Xe 45 chỗ", 1, 1)])
    paired = [r for r in rows if r["matched_cost_line"] == 0]
    assert len(paired) == 1 and paired[0]["actual_vnd"] == 4_000_000 and paired[0]["reason"] == "price_change"  # +370k, not the surcharge amount
    assert any(r["reason"] == "unplanned" and r["category"] == "guide" for r in rows)  # a guide line never pairs with a vehicle


@pytest.fixture
def world(db_session):
    org = OperatorOrg(name="Org A", slug="org-a", settings={})
    db_session.add(org)
    db_session.commit()
    return org, make_user(db_session, "operator", operator_org_id=org.id)


def add_quote(db, org, code, status="won", lines=LINES, price=40_000_000, start="2026-09-10"):
    q = Quote(id=str(uuid4()), org_id=org.id, code=code, status=status, request={"pax": 32, "days": 2, "start_date": start}, itinerary={},
              cost={"lines": lines}, pricing={}, cost_total_vnd=sum(ln["total_vnd"] for ln in lines), price_vnd=price, margin_floor_pct=15,
              received_at=datetime.now(timezone.utc))
    db.add(q)
    db.commit()
    return q


def add_doc(db, org, lines=INVOICE, kind="invoice", status="extracted", supplier="Nhà xe A"):
    doc = OperatorDocument(id=str(uuid4()), org_id=org.id, kind=kind, filename="hd.csv", mime="text/csv", size_bytes=1, sha256=uuid4().hex * 2,
                           storage_path="x", status=status, extracted={"supplier": supplier, "lines": lines})
    db.add(doc)
    db.commit()
    return doc


def post(client, user, path, body=None):
    return client.post(path, json=body, headers=bearer_for(user))


def test_reconcile_edit_confirm_flow(client, world, db_session):
    org, user = world
    q, doc = add_quote(db_session, org, "Q-1"), add_doc(db_session, org)
    r = post(client, user, f"/api/operator/quotes/{q.id}/reconcile", {"document_id": doc.id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rows"]) == 7 and body["finalized"] is False
    quoted, actual = sum(x["total_vnd"] for x in LINES), sum(x["amount_vnd"] for x in INVOICE)
    assert body["totals"] == {"quoted_vnd": quoted, "actual_vnd": actual, "variance_vnd": actual - quoted}
    body = post(client, user, f"/api/operator/quotes/{q.id}/reconcile", {"document_id": doc.id}).json()  # re-run replaces, not duplicates
    assert len(body["rows"]) == 7
    assert db_session.query(CostActual).filter_by(quote_id=q.id).count() == 7
    row = next(x for x in body["rows"] if x["label"] == "Cơm suất (set 6 món)")
    h = bearer_for(user)
    e = client.patch(f"/api/operator/cost-actuals/{row['id']}", json={"actual_vnd": 8_000_000, "reason": "other", "note": "giảm giá"}, headers=h).json()
    assert (e["variance_vnd"], e["reason"], e["note"]) == (320_000, "other", "giảm giá")
    assert client.patch(f"/api/operator/cost-actuals/{row['id']}", json={"reason": "bad"}, headers=h).status_code == 422
    assert q.actual_cost_vnd is None
    c = post(client, user, f"/api/operator/quotes/{q.id}/reconcile/confirm").json()
    db_session.refresh(q)
    assert q.actual_cost_vnd == actual - 320_000 == c["actual_cost_vnd"] and c["finalized"] and all(x["confirmed"] for x in c["rows"])
    assert client.patch(f"/api/operator/cost-actuals/{row['id']}", json={"actual_vnd": 1}, headers=h).status_code == 409
    assert post(client, user, f"/api/operator/quotes/{q.id}/reconcile", {"document_id": doc.id}).status_code == 409
    assert client.get(f"/api/operator/quotes/{q.id}/reconcile", headers=h).json()["finalized"] is True


def test_cannot_reconcile_draft_or_wrong_document(client, world, db_session):
    org, user = world
    doc = add_doc(db_session, org)
    for status in ("draft", "sent", "accepted", "lost"):
        q = add_quote(db_session, org, f"Q-{status}", status=status)
        r = post(client, user, f"/api/operator/quotes/{q.id}/reconcile", {"document_id": doc.id})
        assert r.status_code == 409 and r.json()["error"]["code"] == "QUOTE_NOT_RECONCILABLE", status
    for status in ("won", "deposit_paid"):
        assert post(client, user, f"/api/operator/quotes/{add_quote(db_session, org, f'Q-ok-{status}', status=status).id}/reconcile", {"document_id": doc.id}).status_code == 200
    won = add_quote(db_session, org, "Q-w")
    for bad in (add_doc(db_session, org, kind="rate_sheet"), add_doc(db_session, org, status="uploaded")):
        assert post(client, user, f"/api/operator/quotes/{won.id}/reconcile", {"document_id": bad.id}).status_code == 409
    assert post(client, user, f"/api/operator/quotes/{won.id}/reconcile/confirm").status_code == 422  # nothing reconciled yet
    assert post(client, user, f"/api/operator/quotes/{add_quote(db_session, org, 'Q-d', status='draft').id}/reconcile/confirm").status_code == 409


def test_margin_analytics_numbers(client, world, db_session):
    org, user = world
    one = [{**LINES[0], "total_vnd": 8_000_000, "amount_vnd": 8_000_000, "surcharge_vnd": 0, "label": "Xe"}]
    two = [{**LINES[0], "total_vnd": 15_000_000, "amount_vnd": 15_000_000, "surcharge_vnd": 0, "label": "Xe"}]
    q1 = add_quote(db_session, org, "Q-A", lines=one, price=10_000_000, start="2026-09-10")
    q2 = add_quote(db_session, org, "Q-B", lines=two, price=20_000_000, start="2026-10-10")
    add_quote(db_session, org, "Q-C", lines=one, price=10_000_000)  # won but never reconciled: not in the dashboard
    for q, amount in ((q1, 8_500_000), (q2, 14_000_000)):
        doc = add_doc(db_session, org, [inv("vehicle", "Xe", amount, 1)])
        assert post(client, user, f"/api/operator/quotes/{q.id}/reconcile", {"document_id": doc.id}).status_code == 200
        assert post(client, user, f"/api/operator/quotes/{q.id}/reconcile/confirm").status_code == 200
    h = bearer_for(user)
    a = client.get("/api/operator/analytics/margin", headers=h).json()
    assert [(x["code"], x["expected_margin_pct"], x["actual_margin_pct"], x["variance_vnd"]) for x in a["quotes"]] == [
        ("Q-A", 20.0, 15.0, 500_000), ("Q-B", 25.0, 30.0, -1_000_000)]
    assert a["totals"] == {"quotes": 2, "price_vnd": 30_000_000, "expected_cost_vnd": 23_000_000, "actual_cost_vnd": 22_500_000, "variance_vnd": -500_000,
                           "expected_margin_pct": 23.33, "actual_margin_pct": 25.0}
    assert a["by_reason"] == [{"reason": "price_change", "variance_vnd": -500_000, "count": 2}]
    assert a["by_supplier"] == [{"supplier": "Nhà xe A", "quoted_vnd": 23_000_000, "actual_vnd": 22_500_000, "variance_vnd": -500_000}]
    only = client.get("/api/operator/analytics/margin?from=2026-10-01&to=2026-10-31", headers=h).json()
    assert [x["code"] for x in only["quotes"]] == ["Q-B"] and only["totals"]["variance_vnd"] == -1_000_000
    assert client.get("/api/operator/analytics/margin?from=2027-01-01", headers=h).json()["totals"]["quotes"] == 0


def test_reconciliation_tenancy_and_permissions(client, world, db_session):
    org, user = world
    q, doc = add_quote(db_session, org, "Q-T"), add_doc(db_session, org)
    rows = post(client, user, f"/api/operator/quotes/{q.id}/reconcile", {"document_id": doc.id}).json()["rows"]
    other = OperatorOrg(name="Org B", slug="org-b", settings={})
    db_session.add(other)
    db_session.commit()
    b_user = make_user(db_session, "operator", operator_org_id=other.id)
    b = bearer_for(b_user)
    assert client.get(f"/api/operator/quotes/{q.id}/reconcile", headers=b).status_code == 404
    assert client.post(f"/api/operator/quotes/{q.id}/reconcile", json={"document_id": doc.id}, headers=b).status_code == 404
    assert client.post(f"/api/operator/quotes/{q.id}/reconcile/confirm", headers=b).status_code == 404
    assert client.patch(f"/api/operator/cost-actuals/{rows[0]['id']}", json={"actual_vnd": 1}, headers=b).status_code == 404
    b_quote = add_quote(db_session, other, "Q-B1")
    assert client.post(f"/api/operator/quotes/{b_quote.id}/reconcile", json={"document_id": doc.id}, headers=b).status_code == 404  # A's invoice
    assert client.get("/api/operator/analytics/margin", headers=b).json()["totals"]["quotes"] == 0
    traveler = bearer_for(make_user(db_session, "traveler"))
    assert client.get("/api/operator/analytics/margin", headers=traveler).status_code == 403
    assert client.post(f"/api/operator/quotes/{q.id}/reconcile", json={"document_id": doc.id}, headers=traveler).status_code == 403


def test_demo_history_seed_feeds_the_dashboard_and_is_idempotent(client, db_session):
    from scripts.seed_operator_demo import EMAIL, seed
    from app.models.entities import User
    assert seed(lambda: db_session, history=True)["history"] == 22  # 7 reconciled-or-pending won tours + 15 pipeline quotes
    assert seed(lambda: db_session, history=True)["history"] == 0
    user = db_session.query(User).filter_by(email=EMAIL).one()
    a = client.get("/api/operator/analytics/margin", headers=bearer_for(user)).json()
    assert a["totals"]["quotes"] == 6 and {r["reason"] for r in a["by_reason"]} == {"price_change", "unplanned", "pax_change", "not_used", "surcharge"}
    assert all(q["code"] for q in a["quotes"]) and a["totals"]["variance_vnd"] == sum(q["variance_vnd"] for q in a["quotes"])
    pending = db_session.query(Quote).filter(Quote.raw_message == "DEMO-HISTORY:chua-doi-chieu").one()
    assert pending.status == "won" and pending.actual_cost_vnd is None and pending.customer_name.startswith("[Demo]")
