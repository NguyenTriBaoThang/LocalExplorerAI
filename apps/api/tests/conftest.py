from collections.abc import Generator
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("ROUTING_PROVIDER", "mock")
from geoalchemy2.elements import WKTElement

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Experience, ExperienceSlot, POI, Provider
from app.core.config import settings

# Keep simulation available only to explicit legacy fixtures; runtime defaults to real-only.
settings.real_data_only = False
settings.llm_fallback_enabled = True


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"X-Admin-Key": os.environ["ADMIN_API_KEY"]}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_experience(db_session: Session) -> Experience:
    provider = Provider(name="Demo provider", status="simulated")
    poi = POI(name="Demo craft point", description="Synthetic", district="District 1", latitude=10.775, longitude=106.7, geom=WKTElement("POINT(106.7 10.775)", srid=4326), category="handicraft", address="Demo address", verification_status="simulated")
    experience = Experience(
        poi=poi, provider=provider, name="Paper workshop", description="Simulated workshop",
        intent_tags=["handicraft", "hands_on"], duration_min=60, indoor=True,
        price_basis="per_person", price_vnd=100_000, verification_status="simulated",
    )
    db_session.add(experience)
    db_session.flush()
    return experience


def add_slot(db_session: Session, experience: Experience, start: str = "2030-10-01T02:00:00+00:00", available: int | None = 4, status: str = "available") -> ExperienceSlot:
    from datetime import datetime

    start_at = datetime.fromisoformat(start)
    slot = ExperienceSlot(
        experience_id=experience.id, start_at=start_at,
        end_at=start_at.replace(hour=start_at.hour + 1), capacity_total=10,
        available_reported=available, status=status,
    )
    db_session.add(slot)
    db_session.commit()
    return slot
