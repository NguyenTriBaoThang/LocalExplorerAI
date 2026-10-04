import pytest

from app.models.entities import User
from app.services.auth_service import create_session_token


@pytest.mark.parametrize("role", ["admin", "provider"])
def test_non_traveler_cannot_use_customer_planner_or_chat(client, db_session, sample_experience, role):
    account = User(
        email=f"{role}@example.test",
        display_name=f"Test {role}",
        role=role,
        provider_id=sample_experience.provider_id if role == "provider" else None,
    )
    db_session.add(account)
    db_session.commit()
    client.cookies.set("le_session", create_session_token(account.id))

    plan = client.post("/api/itineraries/plan", json={
        "start_at": "2030-10-01T09:00:00+07:00",
        "end_at": "2030-10-01T16:00:00+07:00",
        "group_size": 1,
        "budget_vnd": 500_000,
        "transport_mode": "driving",
        "intent_weights": {"handicraft": 1.0},
        "locked_experience_ids": [],
    })
    chat = client.post("/api/chat/message", json={"message": "Lên lịch tham quan"})

    assert plan.status_code == 403
    assert plan.json()["error"]["code"] == "ROLE_FORBIDDEN"
    assert chat.status_code == 403
    assert chat.json()["error"]["code"] == "ROLE_FORBIDDEN"
