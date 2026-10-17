"""Install curated heritage stories once; never overwrite editorial changes.

Run after alembic upgrade head. No accounts, bookings or existing catalog rows
are modified. --publish publishes only the newly inserted, sourced sample.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.db.session import SessionLocal
from app.models.entities import LandmarkStory
from app.schemas.landmark_story import LandmarkStoryPayload


def seed(db, publish=False):
    created = []
    for path in sorted((Path(__file__).resolve().parents[1] / "app/data/landmark_stories").glob("*.json")):
        if db.get(LandmarkStory, path.stem):
            continue
        payload = LandmarkStoryPayload.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if payload.overview.status != "sourced" or any(e.status != "sourced" for e in payload.timeline):
            raise ValueError("Curated samples must have sourced overview and timeline")
        data = payload.model_dump(mode="json")
        now = datetime.now(timezone.utc)
        db.add(LandmarkStory(model_id=path.stem, draft=data, published=data if publish else None,
                             revision=1, workflow="published" if publish else "draft",
                             updated_at=now, published_at=now if publish else None))
        created.append(path.stem)
    db.commit()
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        print({"created": seed(db, args.publish)})
