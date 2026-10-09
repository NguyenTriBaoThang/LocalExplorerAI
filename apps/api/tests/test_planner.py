from tests.conftest import add_slot
from app.models.entities import DecisionLog, Experience, ItineraryVersion
from app.schemas.planner import PlanRequest
from app.services.planner_service import PlannerService
from app.services.ml_ranker_service import MLRankerService

PLAN = {
    "start_at": "2030-10-01T09:00:00+07:00",
    "end_at": "2030-10-01T16:00:00+07:00",
    "group_size": 4,
    "budget_vnd": 1_000_000,
    "transport_mode": "driving",
    "intent_weights": {"handicraft": 1.0},
    "locked_experience_ids": [],
}


def test_feasible_plan(client, db_session, sample_experience):
    add_slot(db_session, sample_experience)
    response = client.post("/api/itineraries/plan", json=PLAN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["feasibility_status"] == "feasible"
    assert body["estimated_cost_vnd"] == 400_000
    assert len(body["stops"]) == 1
    version = db_session.query(ItineraryVersion).filter_by(itinerary_id=body["itinerary_id"]).one()
    assert version.version_number == 1
    assert version.stops_snapshot[0]["experience_id"] == sample_experience.id
    decision = db_session.query(DecisionLog).filter_by(itinerary_id=body["itinerary_id"]).one()
    assert decision.new_version == 1
    assert "handicraft" in decision.preserved_intents
    restored = client.get(f"/api/itineraries/{body['itinerary_id']}")
    assert restored.status_code == 200
    assert restored.json()["stops"][0]["experience_id"] == sample_experience.id


def test_planner_uses_ranker_only_to_break_feasible_same_time_ties(db_session, sample_experience):
    add_slot(db_session, sample_experience)
    alternative = Experience(
        poi=sample_experience.poi,
        provider=sample_experience.provider,
        name="Museum visit",
        description="A passive cultural visit",
        intent_tags=["culture"],
        duration_min=60,
        is_hands_on=False,
        is_indoor=True,
        indoor=True,
        price_basis="per_person",
        price_vnd=50_000,
        verification_status="simulated",
    )
    db_session.add(alternative)
    db_session.flush()
    add_slot(db_session, alternative)

    class FakeRanker:
        configured = True

        def rank(self, query, candidates):
            ranked = [
                {**candidate, "rank_score": 1.0 if candidate["candidate_experience_id"] == alternative.id else 0.0}
                for candidate in candidates
            ]
            return ranked, [], {"model_version": "test-ranker-v1"}

    response = PlannerService(db_session, ranker=FakeRanker()).plan(PlanRequest.model_validate(PLAN))
    assert response["stops"][0]["experience_id"] == alternative.id
    assert response["explanation"]["ranking_model_version"] == "test-ranker-v1"

    decision = db_session.query(DecisionLog).filter_by(itinerary_id=response["itinerary_id"]).one()
    assert decision.model_version == "test-ranker-v1"
    assert "ML_RANKER" in decision.reason_codes


def test_planner_uses_versioned_rule_baseline_when_no_deployable_ml_model(db_session, sample_experience):
    add_slot(db_session, sample_experience)
    alternative = Experience(
        poi=sample_experience.poi,
        provider=sample_experience.provider,
        name="Museum visit",
        description="A passive cultural visit",
        intent_tags=["culture"],
        duration_min=60,
        is_hands_on=False,
        is_indoor=True,
        indoor=True,
        price_basis="per_person",
        price_vnd=50_000,
        verification_status="simulated",
    )
    db_session.add(alternative)
    db_session.flush()
    add_slot(db_session, alternative)

    service = PlannerService(db_session, ranker=MLRankerService(__file__))
    response = service.plan(PlanRequest.model_validate(PLAN))

    assert response["stops"][0]["experience_id"] == sample_experience.id
    assert response["explanation"]["ranking_source"] == "rule_baseline"
    assert response["explanation"]["ranking_model_version"] == "rule-baseline-v1"
    decision = db_session.query(DecisionLog).filter_by(itinerary_id=response["itinerary_id"]).one()
    assert "RULE_BASELINE_RANKER" in decision.reason_codes


def test_budget_too_low_returns_no_feasible_plan(client, db_session, sample_experience):
    add_slot(db_session, sample_experience)
    response = client.post("/api/itineraries/plan", json={**PLAN, "budget_vnd": 100_000})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_FEASIBLE_PLAN"


def test_insufficient_capacity_is_rejected(client, db_session, sample_experience):
    add_slot(db_session, sample_experience, available=2)
    response = client.post("/api/itineraries/plan", json=PLAN)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_BOOKABLE_SLOTS"


def test_team_full_slot_status_is_rejected(client, db_session, sample_experience):
    add_slot(db_session, sample_experience, available=8, status="full")
    response = client.post("/api/itineraries/plan", json=PLAN)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_BOOKABLE_SLOTS"


def test_cancelled_slots_return_date_specific_availability_error(client, db_session, sample_experience):
    add_slot(db_session, sample_experience, status="cancelled")

    response = client.post("/api/itineraries/plan", json=PLAN)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_BOOKABLE_SLOTS"
    assert "2030-10-01" in response.json()["error"]["message"]


def test_slot_outside_trip_window_is_rejected(client, db_session, sample_experience):
    add_slot(db_session, sample_experience, start="2030-10-02T09:00:00+07:00")
    response = client.post("/api/itineraries/plan", json=PLAN)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_FEASIBLE_PLAN"


def test_unknown_capacity_is_tentative_not_full(client, db_session, sample_experience):
    add_slot(db_session, sample_experience, available=None, status="tentative")
    response = client.post("/api/itineraries/plan", json=PLAN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["feasibility_status"] == "tentative"
    assert body["stops"][0]["availability_known"] is False
    assert "CAPACITY_UNKNOWN" in body["explanation"]["reason_codes"]
