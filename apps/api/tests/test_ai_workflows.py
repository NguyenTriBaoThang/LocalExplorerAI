from datetime import datetime, timezone

import pytest

from app.adapters.llm.provider import (
    LLMNotConfigured,
    LLMProviderError,
    NotConfiguredLLMProvider,
)
from app.api.dependencies import get_llm_provider
from app.models.entities import (
    POI,
    Event,
    Experience,
    ExperienceSlot,
    Itinerary,
    ItineraryStop,
    Provider,
)
from app.services.offline_chat_fallback import build_offline_constraints


class FakeStructuredProvider:
    model_name = "test-structured"

    def generate(self, system_prompt, user_input, schema):
        if "Travel Needs Parser" in system_prompt:
            return {
                "group_size": 2, "start_time": "09:00", "return_deadline": "16:00", "budget_vnd": 500000,
                "travel_mode": "motorcycle",
                "intent_weights": {"thủ_công": 1.0, "ẩm_thực": 0.0, "văn_hóa": 0.0, "thư_giãn": 0.0},
                "locked_pois": [], "is_complete": True, "missing_fields": [], "clarification_question_vi": None,
            }
        if "Travel Activity Reviewer" in system_prompt:
            return {"experience_id": user_input["experience_id"], "is_hands_on": True, "is_indoor": False,
                    "primary_intent": "thủ_công", "intent_tags": ["handicraft"],
                    "hands_on_justification": "Khách trực tiếp làm sản phẩm.", "weather_sensitivity": "rain_sensitive"}
        if "Travel Experience Comparison Specialist" in system_prompt:
            a, b = user_input["activity_a"], user_input["activity_b"]
            return {"experience_a_id": a["experience_id"], "experience_b_id": b["experience_id"],
                    "semantic_score": 0.9, "tag_overlap_score": 1.0, "final_score": 0.95,
                    "can_substitute_purpose": True, "comparison_reasoning_vi": "Cả hai đều là hoạt động thủ công thực hành."}
        if "Provider Portal Assistant" in system_prompt:
            return {"action": "CANCEL_SLOT", "target_time_window": "09:00 - 10:00", "new_status": "cancelled",
                    "available_reported": 0, "reason_note": "Cơ sở tạm nghỉ.",
                    "confirmation_sms_for_artisan_vi": "Xác nhận hủy ca đã chọn?"}
        if "Itinerary Replanning Advisor" in system_prompt:
            candidates = user_input["solver_feasible_candidates"]
            proposal_items = [{"code": item["code"], "title": item["title"],
                "candidate_experience_id": item["candidate_experience_id"],
                "preserved_intents": item["preserved_intents"], "lost_intents": item["lost_intents"],
                "cost_diff_vnd": item["cost_diff_vnd"], "travel_time_diff_min": item["travel_time_diff_min"],
                "estimated_return_time": item["estimated_return_time"], "is_recommended": index == 0,
                "recommendation_reason_vi": "Giữ được mục đích thủ công và vẫn trong lịch."}
                for index, item in enumerate(candidates)]
            return {"disruption_summary": {"cancelled_experience_title": user_input["cancelled_experience"]["title"],
                    "impact_message_vi": "Ca đã bị hủy."}, "proposals": proposal_items}
        if "Explainable AI (XAI) Engine" in system_prompt:
            return {"headline_vi": "Giữ trải nghiệm thủ công", "core_explanation_vi": "Phương án này giữ mục đích chính. Lịch vẫn nằm trong mốc đã cung cấp.",
                    "trade_off_breakdown": {"why_selected": "Bảo toàn mục đích.", "why_rejected": "So sánh theo dữ liệu solver."},
                    "data_timestamp": user_input["data_timestamp"]}
        if "Machine-Learning Data Labeling Specialist" in system_prompt:
            return {"itinerary_id": user_input["itinerary_id"], "relevance_grade": 3,
                    "rubric_justification_vi": "Review xác nhận khách hoàn thành đúng hoạt động.",
                    "objective_achieved_ratio": 1.0, "is_usable_for_training": True}
        if "Weather Adaptation Advisor" in system_prompt:
            activity_names = [item["title"] for item in user_input["scheduled_outdoor_activities"]]
            return {"weather_condition": "rainy", "indoor_priority_boost": True,
                    "impacted_outdoor_activities": activity_names,
                    "advisory_message_vi": "Ưu tiên hoạt động trong nhà; không có dữ liệu xác minh ngập đường."}
        raise AssertionError("Unrecognized prompt")


def test_all_eight_versioned_prompt_workflows(client, db_session, sample_experience):
    ai = FakeStructuredProvider()
    client.app.dependency_overrides[get_llm_provider] = lambda: ai

    catalog = client.get("/api/ai/prompts")
    assert catalog.status_code == 200
    assert catalog.json()["version"] == "3.0.0"
    assert len(catalog.json()["prompt_ids"]) == 8

    chat = client.post("/api/chat/message", json={"message": "Hai người đi làm gốm, bắt đầu 9 giờ, về trước 16 giờ, ngân sách 500 nghìn."})
    assert chat.status_code == 200
    assert chat.json()["prompt_version"] == "3.0.0"
    assert chat.json()["structured_constraints"]["travel_mode"] == "motorcycle"

    tagged = client.post(f"/api/experiences/{sample_experience.id}/ai-tag", json={})
    assert tagged.status_code == 200, tagged.text
    assert sample_experience.primary_intent == "thủ_công"
    assert sample_experience.tagger_prompt_version == "3.0.0"
    assert sample_experience.indoor is False

    other_provider = Provider(name="Second provider", portal_access_key="provider-test-key")
    other_poi = POI(name="Second craft point", latitude=10.78, longitude=106.71,
                    geom="POINT(106.71 10.78)", category="handicraft", address="Synthetic", verification_status="simulated")
    other = Experience(poi=other_poi, provider=other_provider, name="Basket weaving", title="Basket weaving",
                       description="Make a small basket", intent_tags=["handicraft"], is_hands_on=True,
                       is_indoor=False, indoor=False, duration_min=60, price_basis="per_person", price_vnd=120000,
                       verification_status="simulated")
    db_session.add(other)
    db_session.flush()
    similarity = client.post("/api/ai/intent-similarity", json={"experience_a_id": sample_experience.id, "experience_b_id": other.id})
    assert similarity.status_code == 200, similarity.text
    assert similarity.json()["stored_pair"] == sorted([sample_experience.id, other.id])
    assert similarity.json()["prompt_version"] == "3.0.0"

    slot = ExperienceSlot(experience_id=sample_experience.id,
        start_at=datetime(2030, 10, 1, 2, 0, tzinfo=timezone.utc),
        end_at=datetime(2030, 10, 1, 3, 0, tzinfo=timezone.utc), capacity_total=10,
        available_reported=4, status="open", version=1)
    db_session.add(slot)
    db_session.flush()
    db_session.add(sample_experience.provider)
    sample_experience.provider.portal_access_key = "provider-test-key"
    db_session.commit()
    preview = client.post(f"/api/providers/{sample_experience.provider.id}/slot-assistant/preview",
        headers={"X-Provider-Access-Key": "provider-test-key"},
        json={"message": "Nghỉ ca 9 giờ sáng nay.", "slot_ids": [slot.id]})
    assert preview.status_code == 200, preview.text
    assert preview.json()["requires_explicit_confirmation"] is True
    confirmed = client.post(f"/api/providers/{sample_experience.provider.id}/slot-assistant/confirm",
        headers={"X-Provider-Access-Key": "provider-test-key"},
        json={"confirmation_token": preview.json()["confirmation_token"]})
    assert confirmed.status_code == 200, confirmed.text
    cancellation_event_id = confirmed.json()["event_ids"][0]
    assert slot.status == "cancelled"

    replacement_slot = ExperienceSlot(experience_id=other.id,
        start_at=datetime(2030, 10, 1, 3, 0, tzinfo=timezone.utc),
        end_at=datetime(2030, 10, 1, 4, 0, tzinfo=timezone.utc), capacity_total=8,
        available_reported=4, status="open", version=1)
    itinerary = Itinerary(group_size=1, budget_vnd=500000, start_at=datetime(2030, 10, 1, 2, 0, tzinfo=timezone.utc),
        end_at=datetime(2030, 10, 1, 9, 0, tzinfo=timezone.utc), start_time=datetime(2030, 10, 1, 2, 0, tzinfo=timezone.utc),
        return_deadline=datetime(2030, 10, 1, 9, 0, tzinfo=timezone.utc), travel_mode="motorcycle",
        target_intents={"thủ_công": 1.0}, status="feasible", current_version=1, version=1,
        estimated_cost_vnd=100000, constraints={})
    db_session.add_all([replacement_slot, itinerary])
    db_session.flush()
    affected = ItineraryStop(itinerary_id=itinerary.id, experience_id=sample_experience.id, slot_id=slot.id,
        poi_id=sample_experience.poi_id, stop_order=1, position=1,
        arrival_at=slot.start_at, departure_at=slot.end_at, start_at=slot.start_at, end_at=slot.end_at,
        activity_duration_min=60, cost_vnd=100000, status="planned", is_locked=False, locked=False)
    event = db_session.get(Event, cancellation_event_id)
    event.valid_until = datetime(2030, 10, 1, 9, 0, tzinfo=timezone.utc)
    db_session.add(affected)
    db_session.commit()

    advice = client.post(f"/api/itineraries/{itinerary.id}/replan-advice", json={"event_id": event.id})
    assert advice.status_code == 200, advice.text
    assert advice.json()["prompt_version"] == "3.0.0"
    proposal = advice.json()["proposals"][0]
    accepted = client.post(f"/api/itineraries/{itinerary.id}/replan-advice/accept", json={
        "event_id": event.id, "affected_stop_id": affected.id,
        "candidate_experience_id": other.id, "candidate_slot_id": replacement_slot.id,
        "proposal_code": proposal["code"], "base_version": advice.json()["base_version"],
    })
    assert accepted.status_code == 200, accepted.text

    feedback = client.post(f"/api/itineraries/{itinerary.id}/feedback/label", json={"review_text": "Rất hài lòng, tự tay đan giỏ.", "rating": 5})
    assert feedback.status_code == 200, feedback.text
    assert feedback.json()["label"]["relevance_grade"] == 3

    db_session.expire_all()
    weather = client.post(f"/api/itineraries/{itinerary.id}/weather-advisory", json={
        "rain_mm_per_hour": 14, "aqi_pm25": 80, "temperature_c": 30, "children_in_group": False,
        "observed_at": "2030-10-01T09:00:00+07:00",
    })
    assert weather.status_code == 200, weather.text
    assert weather.json()["advisory"]["indoor_priority_boost"] is True
    assert weather.json()["flood_status_inferred"] is False


def test_missing_llm_is_explicitly_not_configured():
    with pytest.raises(LLMNotConfigured):
        NotConfiguredLLMProvider().generate("template", {}, {})


def test_chat_uses_explicit_offline_fallback_when_llm_is_not_configured(client):
    client.app.dependency_overrides[get_llm_provider] = lambda: NotConfiguredLLMProvider()
    response = client.post("/api/chat/message", json={
        "conversation_id": "fallback-test",
        "message": "Nhóm mình 2 người muốn làm gốm, bắt đầu 9 giờ, về trước 16 giờ, tổng ngân sách 500 nghìn bằng xe máy.",
    })

    assert response.status_code == 200, response.text
    body = response.json()
    constraints = body["structured_constraints"]
    assert body["status"] == "fallback"
    assert body["assistant_mode"] == "local_fallback"
    assert body["fallback_reason"] == "llm_not_configured"
    assert body["prompt_version"] is None
    assert constraints["group_size"] == 2
    assert constraints["start_time"] == "09:00"
    assert constraints["return_deadline"] == "16:00"
    assert constraints["budget_vnd"] == 500_000
    assert constraints["is_complete"] is True
    assert "ngoại tuyến" in body["reply"]


def test_chat_falls_back_on_external_provider_errors(client):
    class BrokenProvider:
        model_name = "broken"

        def generate(self, system_prompt, user_input, schema):
            raise LLMProviderError("upstream unavailable")

    client.app.dependency_overrides[get_llm_provider] = lambda: BrokenProvider()
    response = client.post("/api/chat/message", json={"message": "Mình muốn đi bảo tàng."})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fallback"
    assert body["fallback_reason"] == "llm_unavailable"
    assert body["structured_constraints"]["is_complete"] is False
    assert body["structured_constraints"]["missing_fields"] == [
        "group_size", "start_time", "return_deadline", "budget_vnd",
    ]
    assert "ngoại tuyến" in body["reply"]
    assert body["structured_constraints"]["intent_weights"]["văn_hóa"] == 1.0


def test_offline_parser_does_not_mistake_per_person_price_for_group_budget():
    constraints, _ = build_offline_constraints(
        "Hai người, bắt đầu 9 giờ, về trước 16 giờ, ngân sách 500 nghìn mỗi người.",
        "llm_unavailable",
    )

    assert constraints.budget_vnd is None
    assert constraints.is_complete is False
    assert "budget_vnd" in constraints.missing_fields

