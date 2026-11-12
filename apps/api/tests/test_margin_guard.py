from datetime import date, timedelta

import pytest

from app.api.dependencies import get_llm_provider
from app.models.entities import AuditLog, OperatorOrg, Quote, QuoteRevision, RateCard, RateCardItem
from app.adapters.llm.provider import NotConfiguredLLMProvider
from app.services.quote.cost_engine import QuoteRequestLite, compute_cost
from app.services.quote.explainer import explain_rescue, numbers_grounded, rescue_input
from app.services.quote.vn_calendar import day_flags
from app.services.rate_cards import active_rate_items
from tests.helpers import bearer_for, make_user


@pytest.fixture
def seeded(db_session):
    from scripts.seed_operator_demo import ORG_SLUG, seed
    from app.models.entities import User
    seed(lambda: db_session)
    org = db_session.query(OperatorOrg).filter_by(slug=ORG_SLUG).one()
    return org, db_session.query(User).filter_by(operator_org_id=org.id).one()


@pytest.fixture(autouse=True)
def offline_llm(client):
    client.app.dependency_overrides[get_llm_provider] = lambda: NotConfiguredLLMProvider()


def friday() -> date:
    """First Friday at least 30 days out where Thu, Fri and Sat are ordinary days (Sat only carries the weekend surcharge)."""
    d = date.today() + timedelta(days=30)
    while True:
        if d.weekday() == 4 and not any(day_flags(d + timedelta(days=i))["holiday"] for i in (-1, 0, 1)):
            return d
        d += timedelta(days=1)


def make_quote(client, user, start=None, pax=32):
    start = start or friday()
    r = client.post("/api/operator/quotes", json={"request": {"pax": pax, "days": 2, "start_date": start.isoformat(), "segment": "corporate",
                    "destinations": ["cu_chi", "mekong"]}}, headers=bearer_for(user))
    assert r.status_code == 201, r.text
    return r.json()["quote"]


def patch(client, user, qid, body):
    return client.patch(f"/api/operator/quotes/{qid}", json=body, headers=bearer_for(user))


def send(client, user, qid):
    assert client.post(f"/api/operator/quotes/{qid}/send", headers=bearer_for(user)).status_code == 200


def direct(db, org, q, *, pax=None, depart=None, **lite):
    """compute_cost straight from the quote's stored itinerary, as an independent check of the service."""
    depart = depart or date.fromisoformat(q.request["start_date"])
    return compute_cost(q.itinerary, QuoteRequestLite(pax or q.request["pax"], 2, 3, **lite), active_rate_items(db, org.id, depart), depart).total


def card(db, org, supplier, category, scale=1.0):
    """A draft v+1 of an existing supplier/category with every price multiplied by ``scale``."""
    old = db.query(RateCard).filter_by(org_id=org.id, supplier=supplier, category=category, status="active").one()
    new = RateCard(org_id=org.id, supplier=supplier, category=category, version=old.version + 1, status="draft")
    for i in old.items:
        new.items.append(RateCardItem(org_id=org.id, code=i.code, label=i.label, unit=i.unit, amount_vnd=int(i.amount_vnd * scale) if i.unit != "pct" else i.amount_vnd,
                                      seats=i.seats, max_pax=i.max_pax, conditions=i.conditions))
    db.add(new)
    db.commit()
    return new


# ---- PATCH / reprice ------------------------------------------------------------------------------------------------

def test_draft_pax_change_reoptimizes_price(client, seeded, db_session):
    org, user = seeded
    q = make_quote(client, user)
    r = patch(client, user, q["id"], {"pax": 20})
    assert r.status_code == 200, r.text
    b = r.json()
    row = db_session.get(Quote, q["id"])
    assert b["request"]["pax"] == 20 and b["revision"] == 2
    assert b["cost_total_vnd"] == direct(db_session, org, row, pax=20) < q["cost_total_vnd"]
    assert b["price_vnd"] == b["pricing"]["modes"]["balanced"]["total"] != q["price_vnd"]
    assert b["margin_alert"] is None and b["margin_pct"] >= org.margin_floor_pct
    revs = client.get(f"/api/operator/quotes/{q['id']}/revisions", headers=bearer_for(user)).json()
    assert [x["revision"] for x in revs] == [2, 1] and "pax 20" in revs[0]["reason"]


def test_sent_quote_keeps_price_and_alerts_below_floor(client, seeded, db_session):
    org, user = seeded
    q = make_quote(client, user)
    send(client, user, q["id"])
    r = patch(client, user, q["id"], {"pax": 60, "reason": "Khách thêm người"}).json()
    row = db_session.get(Quote, q["id"])
    assert r["price_vnd"] == q["price_vnd"] and r["status"] == "sent"  # the price the customer saw does not move
    assert r["cost_total_vnd"] == direct(db_session, org, row, pax=60) > q["cost_total_vnd"]
    m = (q["price_vnd"] - r["cost_total_vnd"]) / q["price_vnd"] * 100
    alert = r["margin_alert"]
    assert alert and alert["margin_pct"] == round(m, 2) < org.margin_floor_pct == alert["floor_pct"]
    need = -(-r["cost_total_vnd"] * 100 // (100 - org.margin_floor_pct))
    assert alert["shortfall_vnd"] == need - q["price_vnd"] > 0
    log = db_session.query(AuditLog).filter_by(target_id=q["id"], action="quote.margin_alert").one()
    assert log.details["margin_pct"] == alert["margin_pct"] and log.details["reason"] == "Khách thêm người"
    assert client.get(f"/api/operator/quotes/{q['id']}", headers=bearer_for(user)).json()["margin_alert"] == alert
    assert db_session.query(QuoteRevision).filter_by(quote_id=q["id"]).count() == 2


def test_patch_date_itinerary_and_validation(client, seeded, db_session):
    org, user = seeded
    q = make_quote(client, user)
    fri = friday()
    r = patch(client, user, q["id"], {"start_date": (fri + timedelta(days=-1)).isoformat()}).json()
    assert r["request"]["start_date"] == (fri - timedelta(days=1)).isoformat()
    assert r["cost_total_vnd"] < q["cost_total_vnd"]  # Thu-Fri avoids the Saturday weekend surcharge
    days = [{"title": d["title"], "legs": [{"from": l["from"], "to": l["to"], "distance_km": l["distance_km"] + 50} for l in d["legs"]],
             "stops": d["stops"]} for d in q["itinerary"]["days"]]
    r2 = patch(client, user, q["id"], {"itinerary_days": days}).json()
    assert r2["cost_total_vnd"] > r["cost_total_vnd"]
    assert patch(client, user, q["id"], {"itinerary_days": days[:1]}).status_code == 422
    assert patch(client, user, q["id"], {}).status_code == 422
    assert patch(client, user, q["id"], {"pax": 99}).status_code == 422
    client.post(f"/api/operator/quotes/{q['id']}/mark", json={"outcome": "lost"}, headers=bearer_for(user))
    assert patch(client, user, q["id"], {"pax": 10}).status_code == 409


# ---- rate card approve hook -----------------------------------------------------------------------------------------

def test_approve_recosts_only_affected_open_quotes(client, seeded, db_session):
    org, user = seeded
    draft, sent, lost, past = (make_quote(client, user), make_quote(client, user), make_quote(client, user), make_quote(client, user, date(2026, 4, 30)))
    send(client, user, sent["id"])
    client.post(f"/api/operator/quotes/{lost['id']}/mark", json={"outcome": "lost"}, headers=bearer_for(user))
    other = OperatorOrg(name="Org B", slug="org-b", settings={})
    db_session.add(other)
    db_session.commit()
    b_user = make_user(db_session, "operator", operator_org_id=other.id)
    h = bearer_for(user)

    # A supplier none of the quotes used (Vũng Tàu hotel; the Mekong template pins its own room): nothing to re-cost.
    unrelated = card(db_session, org, "KS Biển Xanh Vũng Tàu 3★", "hotel", 2)
    r = client.post(f"/api/operator/rate-cards/{unrelated.id}/approve", headers=h)
    assert r.status_code == 200 and r.json()["requote"] == {"requoted": 0, "quotes": [], "alerts": []}

    new = card(db_session, org, "Nhà xe Phương Nam", "vehicle", 4)
    r = client.post(f"/api/operator/rate-cards/{new.id}/approve", headers=h).json()["requote"]
    assert r["requoted"] == 2 and {x["quote_id"] for x in r["quotes"]} == {draft["id"], sent["id"]}
    for x in r["quotes"]:
        assert x["new_cost_vnd"] > x["old_cost_vnd"]
    got = {x["quote_id"]: db_session.get(Quote, x["quote_id"]) for x in r["quotes"]}
    assert got[sent["id"]].price_vnd == sent["price_vnd"] and got[sent["id"]].revision == 2  # sent keeps its price
    assert got[draft["id"]].price_vnd > draft["price_vnd"]  # draft is re-priced
    assert {a["quote_id"] for a in r["alerts"]} == {sent["id"]}  # only the price-locked quote falls below the floor
    assert r["alerts"][0]["shortfall_vnd"] > 0
    assert db_session.query(AuditLog).filter_by(target_id=sent["id"], action="quote.margin_alert").count() == 1
    for q in (lost, past):  # closed / already departed: untouched
        row = db_session.get(Quote, q["id"])
        db_session.refresh(row)
        assert row.revision == 1 and row.cost_total_vnd == q["cost_total_vnd"]

    # another org approving the same supplier name leaves org A alone
    b_old = RateCard(org_id=other.id, supplier="Nhà xe Phương Nam", category="vehicle", version=1, status="draft")
    b_old.items.append(RateCardItem(org_id=other.id, code="vehicle-45s-per_day", label="Xe 45", unit="per_day", amount_vnd=1, seats=45, conditions={}))
    db_session.add(b_old)
    db_session.commit()
    assert client.post(f"/api/operator/rate-cards/{b_old.id}/approve", headers=bearer_for(b_user)).json()["requote"]["requoted"] == 0
    assert db_session.get(Quote, sent["id"]).revision == 2


# ---- rescue ---------------------------------------------------------------------------------------------------------

def rescue_scenario(client, user):
    """Friday quote with the pricey meal/vehicle/hotel pins, sent, then 60 guests: margin goes under the floor."""
    q = make_quote(client, user)
    assert patch(client, user, q["id"], {"overrides": {"vehicle_seats": 16, "meal_code": "meal-hai-san"}}).status_code == 200
    send(client, user, q["id"])
    assert patch(client, user, q["id"], {"pax": 60}).json()["margin_alert"]
    return q["id"]


def test_each_rescue_option_matches_a_direct_recomputation(client, seeded, db_session):
    org, user = seeded
    qid = rescue_scenario(client, user)
    body = client.get(f"/api/operator/quotes/{qid}/rescue", headers=bearer_for(user)).json()
    q = db_session.get(Quote, qid)
    options = {o["code"]: o for o in body["options"]}
    assert set(options) == {"vehicle_optimal", "shift_date", "meal_tier", "hotel_tier", "raise_price"}
    assert body["explanation_source"] == "template" and numbers_grounded(body["explanation"], rescue_input(body["margin_alert"], body["options"]))
    pin = {"vehicle_seats": 16, "meal_code": "meal-hai-san"}
    assert direct(db_session, org, q, **pin) == q.cost_total_vnd
    for o in body["options"]:
        assert o["new_margin_pct"] == round((o["new_price_vnd"] - o["new_cost_vnd"]) / o["new_price_vnd"] * 100, 2)
        if o["code"] != "raise_price":
            assert o["savings_vnd"] == q.cost_total_vnd - o["new_cost_vnd"] > 0 and o["new_price_vnd"] == q.price_vnd
    assert options["vehicle_optimal"]["new_cost_vnd"] == direct(db_session, org, q, meal_code="meal-hai-san")
    assert options["meal_tier"]["new_cost_vnd"] == direct(db_session, org, q, vehicle_seats=16, meal_code="meal-com-suat")
    assert options["hotel_tier"]["new_cost_vnd"] == direct(db_session, org, q, **pin, hotel_code="hotel-mekong-homestay")
    shifted = date.fromisoformat(options["shift_date"]["changes"]["start_date"])
    assert abs((shifted - date.fromisoformat(q.request["start_date"])).days) <= 3 and shifted >= date.today()
    assert options["shift_date"]["new_cost_vnd"] == direct(db_session, org, q, depart=shifted, **pin)
    rp = options["raise_price"]
    assert rp["savings_vnd"] == 0 and rp["new_margin_pct"] >= org.margin_floor_pct and rp["new_price_vnd"] % (10_000 * 60) == 0
    need = -(-q.cost_total_vnd * 100 // (100 - org.margin_floor_pct))
    assert rp["new_price_vnd"] - 10_000 * 60 < need <= rp["new_price_vnd"]  # smallest 10k/guest step that restores the floor
    assert 0 < rp["p_win"] <= 1
    assert [o["savings_vnd"] for o in body["options"][:-1]] == sorted((o["savings_vnd"] for o in body["options"][:-1]), reverse=True)


def test_apply_rescue_creates_revision_and_keeps_price(client, seeded, db_session):
    org, user = seeded
    qid = rescue_scenario(client, user)
    q = db_session.get(Quote, qid)
    price, before = q.price_vnd, q.revision
    r = client.post(f"/api/operator/quotes/{qid}/apply-rescue/vehicle_optimal", headers=bearer_for(user))
    assert r.status_code == 200 and r.json()["applied"] is True and r.json()["requires_resend"] is False
    db_session.refresh(q)
    assert q.revision == before + 1 and q.price_vnd == price and q.status == "sent"
    assert q.cost_total_vnd == r.json()["option"]["new_cost_vnd"] and q.request["overrides"] == {"meal_code": "meal-hai-san"}
    revs = client.get(f"/api/operator/quotes/{qid}/revisions", headers=bearer_for(user)).json()
    assert revs[0]["revision"] == before + 1 and revs[0]["reason"].startswith("Cứu margin")
    assert db_session.query(AuditLog).filter_by(target_id=qid, action="quote.rescue_applied").count() == 1
    assert client.post(f"/api/operator/quotes/{qid}/apply-rescue/nope", headers=bearer_for(user)).status_code == 404


def test_raise_price_on_sent_quote_needs_resend(client, seeded, db_session):
    org, user = seeded
    qid = rescue_scenario(client, user)
    q = db_session.get(Quote, qid)
    price, before = q.price_vnd, q.revision
    r = client.post(f"/api/operator/quotes/{qid}/apply-rescue/raise_price", headers=bearer_for(user)).json()
    assert r["applied"] is False and r["requires_resend"] is True and r["suggested_price_vnd"] > price
    db_session.refresh(q)
    assert q.price_vnd == price and q.revision == before and q.status == "sent" and q.public_token_hash  # nothing changed
    ok = client.post(f"/api/operator/quotes/{qid}/apply-rescue/raise_price", json={"confirm_resend": True}, headers=bearer_for(user)).json()
    db_session.refresh(q)
    assert ok["applied"] and ok["requires_resend"] and q.price_vnd == ok["suggested_price_vnd"] and q.revision == before + 1
    assert q.status == "draft" and q.public_token_hash is None  # old link revoked until the operator sends again
    assert ok["quote"]["margin_alert"] is None
    # once the customer accepted, a price/date/tier change is refused outright
    q2 = db_session.get(Quote, rescue_scenario(client, user))
    q2.status = "accepted"
    db_session.commit()
    assert client.post(f"/api/operator/quotes/{q2.id}/apply-rescue/raise_price", json={"confirm_resend": True}, headers=bearer_for(user)).status_code == 409
    assert client.post(f"/api/operator/quotes/{q2.id}/apply-rescue/vehicle_optimal", headers=bearer_for(user)).status_code == 200  # cost-side: fine


def test_rescue_explainer_falls_back_when_numbers_are_invented(seeded):
    class Liar:
        model_name = "x"

        def generate(self, *a, **k):
            return {"explanation": "Giảm 999.999 đồng"}

    alert = {"margin_pct": 9.5, "floor_pct": 15, "shortfall_vnd": 1_000_000}
    text, source = explain_rescue(Liar(), alert, [{"title": "Dời ngày", "savings_vnd": 500_000, "new_margin_pct": 12.0}])
    assert source == "template" and "999" not in text and "500.000" in text


def test_margin_guard_tenancy(client, seeded, db_session):
    org, user = seeded
    q = make_quote(client, user)
    other = OperatorOrg(name="Org C", slug="org-c", settings={})
    db_session.add(other)
    db_session.commit()
    b = bearer_for(make_user(db_session, "operator", operator_org_id=other.id))
    assert client.patch(f"/api/operator/quotes/{q['id']}", json={"pax": 10}, headers=b).status_code == 404
    for method, path in [("get", "/rescue"), ("get", "/revisions"), ("post", "/apply-rescue/shift_date")]:
        assert getattr(client, method)(f"/api/operator/quotes/{q['id']}{path}", headers=b).status_code == 404, path
    traveler = bearer_for(make_user(db_session, "traveler"))
    assert client.patch(f"/api/operator/quotes/{q['id']}", json={"pax": 10}, headers=traveler).status_code == 403
