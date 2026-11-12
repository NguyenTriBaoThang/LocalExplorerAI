from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.entities import OperatorOrg, Quote
from tests.helpers import bearer_for, make_user

T0 = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
URL = "/api/operator/analytics/roi"


def _org(db, name):
    org = OperatorOrg(name=name, slug=name.lower(), settings={})  # defaults: markup 25%, OTA 18%, manual 90 min
    db.add(org)
    db.commit()
    return org


def _q(db, org, code, status, price, cost, respond=None, created_lag=0, start="2026-09-10"):
    db.add(Quote(id=str(uuid4()), org_id=org.id, code=code, status=status, request={"start_date": start}, cost={"lines": []}, cost_total_vnd=cost,
                 price_vnd=price, received_at=T0, created_at=T0 + timedelta(minutes=created_lag),
                 sent_at=None if respond is None else T0 + timedelta(minutes=respond)))
    db.commit()


def _fixture(db, org):
    _q(db, org, "A", "won", 12_000_000, 8_000_000, respond=10, created_lag=1)           # response 10, saved 90-9 = 81
    _q(db, org, "B", "deposit_paid", 10_000_000, 7_000_000, respond=20)                   # response 20, saved 70
    _q(db, org, "C", "lost", 9_000_000, 6_000_000, respond=30)                            # response 30, saved 60
    _q(db, org, "D", "sent", 9_000_000, 6_000_000, respond=200)                           # response 200, saved clamped to 0
    _q(db, org, "E", "draft", None, 5_000_000)                                            # not sent: excluded from time stats


def test_roi_hand_computed(client, db_session):
    org, other = _org(db_session, "OrgA"), _org(db_session, "OrgB")
    _fixture(db_session, org)
    _q(db_session, other, "X", "won", 99_000_000, 1_000_000, respond=1)  # tenancy: must not leak
    op = make_user(db_session, "operator", operator_org_id=org.id)
    d = client.get(URL, headers=bearer_for(op)).json()
    assert (d["quotes_count"], d["sent_count"], d["won_count"], d["lost_count"]) == (5, 4, 2, 1)
    assert d["median_response_minutes"]["value"] == 25.0           # median(10, 20, 30, 200)
    assert d["hours_saved"]["value"] == 3.52                        # (81 + 70 + 60 + 0) / 60
    assert d["win_rate"]["value"] == 0.6667                         # 2 / (2 + 1)
    assert d["margin_uplift_vnd"]["value"] == 3_250_000             # (12M - 10M) + (10M - 8.75M)
    assert d["margin_uplift_vnd"]["pct_of_fixed_markup_profit"] == 86.67  # / (2M + 1.75M)
    assert d["ota_commission_avoided_vnd"]["value"] == 3_960_000    # 22M * 18%
    assert all("basis" in d[k] for k in ("median_response_minutes", "hours_saved", "win_rate", "margin_uplift_vnd", "ota_commission_avoided_vnd"))
    # date filter by tour start date
    assert client.get(URL, params={"from": "2026-10-01"}, headers=bearer_for(op)).json()["quotes_count"] == 0


def test_roi_empty_org_is_null_not_error(client, db_session):
    op = make_user(db_session, "operator", operator_org_id=_org(db_session, "Empty").id)
    res = client.get(URL, headers=bearer_for(op))
    assert res.status_code == 200
    d = res.json()
    assert d["quotes_count"] == 0
    for k in ("median_response_minutes", "hours_saved", "win_rate", "margin_uplift_vnd", "ota_commission_avoided_vnd"):
        assert d[k]["value"] is None
    assert d["margin_uplift_vnd"]["pct_of_fixed_markup_profit"] is None


def test_roi_backtest_block_is_synthetic(client, db_session):
    op = make_user(db_session, "operator", operator_org_id=_org(db_session, "Bt").id)
    bt = client.get(URL, headers=bearer_for(op)).json()["backtest"]
    assert bt is not None and bt["dataset_status"] == "synthetic"
    by_key = {s["key"]: s for s in bt["strategies"]}
    assert list(by_key) == ["fixed_25pct_markup", "optimizer_balanced", "optimizer_max_profit", "oracle_max_profit_true_p"]
    assert by_key["fixed_25pct_markup"]["profit_vs_baseline_pct"] == 0.0
    assert by_key["oracle_max_profit_true_p"]["profit_vs_baseline_pct"] > by_key["optimizer_balanced"]["profit_vs_baseline_pct"] > 0


def test_roi_forbidden_for_traveler(client, db_session):
    assert client.get(URL, headers=bearer_for(make_user(db_session, "traveler"))).status_code == 403
