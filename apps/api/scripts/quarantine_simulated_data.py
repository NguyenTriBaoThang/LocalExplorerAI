"""Hide existing demo catalog rows without deleting user data.

Run from apps/api. Defaults to a read-only preview; pass --apply to commit.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import or_, select

from app.db.session import SessionLocal
from app.models.entities import AuditLog, Experience, ExperienceSlot, POI, Provider


def quarantine(apply: bool = False) -> dict[str, int]:
    with SessionLocal() as db:
        simulated_pois = db.scalars(select(POI).where(POI.verification_status == "simulated")).all()
        simulated_experiences = db.scalars(
            select(Experience).where(Experience.verification_status == "simulated")
        ).all()
        experience_ids = [item.id for item in simulated_experiences]
        slots = db.scalars(
            select(ExperienceSlot).where(ExperienceSlot.experience_id.in_(experience_ids))
        ).all() if experience_ids else []
        simulated_providers = db.scalars(select(Provider).where(or_(
            Provider.verification_status.in_(["mock", "simulated"]),
            Provider.status == "simulated",
        ))).all()

        counts = {
            "pois": len(simulated_pois),
            "experiences": len(simulated_experiences),
            "slots": len(slots),
            "providers": len(simulated_providers),
        }
        if not apply or not any(counts.values()):
            return counts

        for item in simulated_pois:
            item.verification_status = "hidden"
        for item in simulated_experiences:
            item.verification_status = "hidden"
        for slot in slots:
            slot.status = "cancelled"
            slot.available_reported = 0
        for provider in simulated_providers:
            provider.verification_status = "hidden"
            provider.status = "inactive"
            provider.is_active = False

        db.add(AuditLog(
            id=str(uuid4()),
            actor_id=None,
            action="simulated_catalog.quarantined",
            target_type="dataset",
            target_id="simulated-seed-catalog",
            details={"counts": counts, "data_preserved": True},
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
        return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Quarantine rows after reviewing the counts.")
    arguments = parser.parse_args()
    result = quarantine(apply=arguments.apply)
    print(("Quarantined" if arguments.apply else "Would quarantine") + f" {result}; original rows are preserved.")
