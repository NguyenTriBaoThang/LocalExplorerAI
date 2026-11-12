from datetime import date

import pytest

from app.adapters.llm.provider import LLMProviderError, NotConfiguredLLMProvider
from app.api.dependencies import get_llm_provider
from app.models.entities import AuditLog, OperatorOrg, Quote, QuoteRevision, TourTemplate
from app.services.quote.explainer import explain, explain_input, numbers_grounded, template_explanation
from app.services.quote.quote_service import select_template
from app.services.quote.request_parser import QuoteRequest, parse_offline, parse_request
from tests.helpers import bearer_for, make_user

TODAY = date(2026, 4, 1)
DEMO = "Công ty mình 32 người muốn đi Củ Chi – Mekong 2 ngày 1 đêm, khởi hành 30/4/2026, ngân sách tầm 2 triệu/người"


class FakeLLM:
    """Parser returns a fixed request; explainer returns ``explanation`` (default: invents a number)."""
    model_name = "fake"

    def __init__(self, explanation="Mức này hợp lý vì giá vốn 999.999.999đ.", request=None):
        self.explanation, self.request, self.prompts = explanation, request, []

    def generate(self, system_prompt, user_input, schema, attachments=()):
        if "tách thành yêu cầu báo giá" in system_prompt:
            self.prompts.append("parser")
            if self.request is None:
                raise LLMProviderError("down")
            return self.request
        self.prompts.append("explainer")
        return {"explanation": self.explanation}


DEMO_REQ = {"pax": 32, "days": 2, "start_date": "2026-04-30", "segment": "corporate", "destinations": ["cu_chi", "mekong"],
            "budget_per_pax": 2_000_000}


@pytest.fixture
def seeded(db_session):
    from scripts.seed_operator_demo import ORG_SLUG, seed
    seed(lambda: db_session)
    org = db_session.query(OperatorOrg).filter_by(slug=ORG_SLUG).one()
    from app.models.entities import User
    return org, db_session.query(User).filter_by(operator_org_id=org.id).one()


@pytest.fixture
def llm(client):
    fake = FakeLLM()
    client.app.dependency_overrides[get_llm_provider] = lambda: fake
    return fake


def post(client, user, body):
    return client.post("/api/operator/quotes", json=body, headers=bearer_for(user))


# ---- parser -------------------------------------------------------------------------------------------------------

def test_offline_parser_reads_demo_message():
    r = parse_offline(DEMO, TODAY)
    assert (r.pax, r.days, r.start_date, r.segment) == (32, 2, date(2026, 4, 30), "corporate")
    assert r.destinations == ["cu_chi", "mekong"] and r.budget_per_pax == 2_000_000 and r.missing_fields == []


def test_offline_parser_year_rollover_missing_and_out_of_range():
    assert parse_offline("32 khách đi Củ Chi 1 ngày 30/4", date(2026, 5, 1)).start_date == date(2027, 4, 30)
    r = parse_offline("đoàn 100 người đi Vũng Tàu", TODAY)
    assert r.pax is None and set(r.missing_fields) == {"pax", "days", "start_date"}
    assert r.segment == "family" and r.assumed_fields == ["segment"]


def test_parser_falls_back_when_llm_fails_or_is_not_configured():
    for provider in (NotConfiguredLLMProvider(), FakeLLM()):
        req, source = parse_request(provider, DEMO, TODAY)
        assert source == "offline" and req.pax == 32
    req, source = parse_request(FakeLLM(request={**DEMO_REQ, "missing_fields": ["bịa"]}), "x", TODAY)
    assert source == "llm" and req.missing_fields == []  # missing_fields is recomputed, never trusted


# ---- template selection ---------------------------------------------------------------------------------------------

def test_template_selection_is_deterministic(seeded, db_session):
    ts = list(reversed(db_session.query(TourTemplate).all()))  # input order must not matter
    pick = lambda **kw: (lambda t: t and t.code)(select_template(ts, QuoteRequest(**kw)))
    assert pick(days=2, destinations=["cu_chi", "mekong"]) == "cu-chi-mekong-2n1d"
    assert pick(days=1, destinations=["cu_chi"]) == "cu-chi-1n"
    assert pick(days=1, destinations=["cu_chi", "mekong"]) == "cu-chi-1n"  # tie on overlap -> lowest code
    assert pick(days=2, destinations=["vung_tau"]) == "vung-tau-2n1d"
    assert pick(days=1, destinations=["vung_tau"]) is None  # no 1-day Vũng Tàu: custom tour


# ---- end to end -----------------------------------------------------------------------------------------------------

def test_demo_message_end_to_end(client, seeded, llm, db_session):
    _, user = seeded
    r = post(client, user, {"message": DEMO})
    assert r.status_code == 201, r.text
    q = r.json()["quote"]
    assert r.json()["parser"] == "offline" and q["code"].startswith("Q-") and q["status"] == "draft"
    assert any("surcharge-holiday" in ln["surcharge_codes"] for ln in q["cost"]["lines"])  # 30/4 is a holiday
    assert [s["code"] for s in q["cost"]["surcharges"]] and q["cost"]["fixed_total"] + q["cost"]["variable_total"] == q["cost"]["total"]
    modes = q["pricing"]["modes"]
    assert modes["safe"]["price_per_pax"] <= modes["balanced"]["price_per_pax"] <= modes["max_profit"]["price_per_pax"]
    assert all(m["margin_pct"] >= q["margin_floor_pct"] for m in modes.values())
    assert q["price_vnd"] == modes["balanced"]["total"] and q["pricing"]["source"] == "heuristic"
    assert "999.999.999" not in q["explanation"]  # invented number discarded by the guard
    assert db_session.query(QuoteRevision).filter_by(quote_id=q["id"]).count() == 1
    assert db_session.query(AuditLog).filter_by(target_type="quote", target_id=q["id"], action="quote.created").count() == 1
    assert post(client, user, {"message": DEMO}).json()["quote"]["code"].endswith("0002")


def test_missing_fields_return_questions_not_a_price(client, seeded, llm, db_session):
    _, user = seeded
    r = post(client, user, {"message": "cho mình hỏi giá tour Củ Chi"})
    assert r.status_code == 200
    body = r.json()
    assert body["quote"] is None and len(body["questions"]) == 3 and all("?" in q for q in body["questions"])
    assert db_session.query(Quote).count() == 0


def test_parse_only_and_confirmed_request(client, seeded, llm, db_session):
    _, user = seeded
    r = post(client, user, {"message": DEMO, "parse_only": True})
    assert r.status_code == 200 and r.json()["quote"] is None and r.json()["request"]["pax"] == 32
    assert db_session.query(Quote).count() == 0
    edited = {**r.json()["request"], "pax": 40}
    q = post(client, user, {"message": DEMO, "request": edited}).json()["quote"]
    assert q["request"]["pax"] == 40
    assert post(client, user, {}).status_code == 422


def test_custom_tour_is_not_supported(client, seeded, llm):
    _, user = seeded
    r = post(client, user, {"request": {**DEMO_REQ, "days": 1, "destinations": ["vung_tau"]}})
    assert r.status_code == 501 and r.json()["error"]["code"] == "CUSTOM_TOUR_UNSUPPORTED"


def test_llm_explanation_kept_when_numbers_are_grounded(client, seeded, db_session):
    org, user = seeded
    q = post(client, user, {"request": DEMO_REQ}).json()["quote"]
    m = q["pricing"]["modes"]["balanced"]
    good = FakeLLM(f"Giá {m['price_per_pax']:,}đ/khách cho {q['request']['pax']} khách.".replace(",", "."))
    client.app.dependency_overrides[get_llm_provider] = lambda: good
    r = client.post(f"/api/operator/quotes/{q['id']}/select-mode", json={"mode": "balanced"}, headers=bearer_for(user))
    assert r.json()["explanation"].startswith("Giá ") and good.prompts == ["explainer"]


# ---- explanation guard ----------------------------------------------------------------------------------------------

SRC = {"price": 1_250_000, "total": 40_000_000, "margin_pct": 20.4, "p": 62, "pax": 32, "labels": ["Xe 45 chỗ"], "date": "2026-04-30"}


@pytest.mark.parametrize("text,ok", [
    ("Giá 1.250.000đ cho 32 khách", True),
    ("Giá 1,25 triệu mỗi khách, tổng 40 triệu", True),
    ("Giá 1.200.000đ", False),
    ("Biên 20% và xác suất 62%", True),
    ("Biên 20,4% nhưng xác suất 75%", False),
    ("Xe 45 chỗ, khởi hành 30/4", True),
    ("Giảm 850k so với đối thủ", False),
    ("Không có con số nào", True),
])
def test_number_guard(text, ok):
    assert numbers_grounded(text, SRC) is ok


def test_template_explanation_passes_its_own_guard_and_fallback_used(seeded):
    pricing = {"modes": {k: {"price_per_pax": 1_250_000, "total": 40_000_000, "margin_pct": 20.37, "p_win": 0.62, "expected_profit": 5e6,
                             "floor_bound": k == "safe"} for k in ("safe", "balanced", "max_profit")}}
    cost = {"total": 32_000_000, "lines": [{"label": "Xe 45 chỗ", "total_vnd": 9_000_000}, {"label": "Ăn", "total_vnd": 8_000_000}],
            "surcharges": [{"label": "Phụ thu ngày lễ", "amount_vnd": 1_000_000}]}
    for mode in pricing["modes"]:
        src = explain_input({"pax": 32, "days": 2}, cost, pricing, mode)
        assert numbers_grounded(template_explanation(src), src)
    text, source = explain(FakeLLM("Bịa 12345 đồng"), {"pax": 32, "days": 2}, cost, pricing, "balanced")
    assert source == "template" and "12345" not in text
    text, source = explain(NotConfiguredLLMProvider(), {"pax": 32, "days": 2}, cost, pricing, "safe")
    assert source == "template" and "Không mức giá nào" in text


# ---- select-mode / mark / curve / tenancy ---------------------------------------------------------------------------

def test_select_mode_mark_and_curve(client, seeded, llm, db_session):
    _, user = seeded
    q = post(client, user, {"request": DEMO_REQ}).json()["quote"]
    h = bearer_for(user)
    s = client.post(f"/api/operator/quotes/{q['id']}/select-mode", json={"mode": "safe"}, headers=h).json()
    assert s["price_mode"] == "safe" and s["price_vnd"] == q["pricing"]["modes"]["safe"]["total"] and s["revision"] == 2
    assert client.post(f"/api/operator/quotes/{q['id']}/select-mode", json={"mode": "x"}, headers=h).status_code == 422
    curve = client.get(f"/api/operator/quotes/{q['id']}/pricing-curve", headers=h).json()
    prices = [p["price_per_pax"] for p in curve["points"]]
    assert prices == sorted(prices) and len(prices) > 5 and set(curve["points"][0]) == {"price_per_pax", "p_win", "expected_profit"}
    assert curve["selected_mode"] == "safe" and curve["modes"]["balanced"]["price_per_pax"] in prices
    ps = [p["p_win"] for p in curve["points"]]
    assert ps == sorted(ps, reverse=True)  # P falls with price
    assert client.post(f"/api/operator/quotes/{q['id']}/mark", json={"outcome": "lost", "reason": "đối thủ rẻ hơn"}, headers=h).json()["status"] == "lost"
    assert client.post(f"/api/operator/quotes/{q['id']}/mark", json={"outcome": "won"}, headers=h).status_code == 409
    assert client.post(f"/api/operator/quotes/{q['id']}/select-mode", json={"mode": "balanced"}, headers=h).status_code == 409
    assert [x["status"] for x in client.get("/api/operator/quotes?status=lost", headers=h).json()] == ["lost"]
    assert client.get("/api/operator/quotes?status=draft&needs_followup=true", headers=h).json() == []


def test_tenancy_org_b_cannot_see_org_a_quotes(client, seeded, llm, db_session):
    _, user = seeded
    q = post(client, user, {"request": DEMO_REQ}).json()["quote"]
    other = OperatorOrg(name="Org B", slug="org-b", settings={})
    db_session.add(other)
    db_session.commit()
    b = bearer_for(make_user(db_session, "operator", operator_org_id=other.id))
    assert client.get("/api/operator/quotes", headers=b).json() == []
    for method, path, body in [("get", "", None), ("get", "/pricing-curve", None), ("post", "/select-mode", {"mode": "safe"}),
                               ("post", "/mark", {"outcome": "won"})]:
        r = getattr(client, method)(f"/api/operator/quotes/{q['id']}{path}", headers=b, **({"json": body} if body else {}))
        assert r.status_code == 404, path
    # org B has no rate cards: a draft attempt fails cleanly, not with another org's prices
    assert post(client, make_user(db_session, "operator", operator_org_id=other.id), {"request": DEMO_REQ}).status_code in (422, 501)
    assert client.get("/api/operator/quotes", headers=bearer_for(make_user(db_session, "traveler"))).status_code == 403
