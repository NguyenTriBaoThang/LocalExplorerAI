import os
import re
import secrets
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import User, Itinerary, ItineraryStop, POI, Experience, ExperienceSlot
from app.auth import hash_password
from app.services.account_tokens import issue_claim_token

PROD_DOMAIN = "https://www.localexplorerai.site"
LOCAL_DOMAIN = "http://localhost:8080"

SCHEDULE_TIMELINE = [
    {"hour_start": 8, "minute_start": 30, "duration": 90},
    {"hour_start": 10, "minute_start": 15, "duration": 120},
    {"hour_start": 12, "minute_start": 30, "duration": 120},
    {"hour_start": 15, "minute_start": 0, "duration": 120},
]


SHADOW_EMAIL_PREFIX = "zalo_"
SHADOW_EMAIL_DOMAIN = "localexplorer.site"


def is_shadow_email(email: str | None) -> bool:
    """Addresses reserved for the placeholder accounts the chat bot creates; nobody can register or log in as one."""
    value = (email or "").strip().lower()
    return value.startswith(SHADOW_EMAIL_PREFIX) and value.endswith("@" + SHADOW_EMAIL_DOMAIN)


class TicketService:
    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def _get_db(self) -> Session:
        return self._db if self._db is not None else SessionLocal()

    def get_or_create_shadow_user(self, db: Session, chat_id: str, display_name: str) -> User:
        """Find or create an underlying shadow traveler account for this Zalo chat."""
        clean_id = str(chat_id).replace("-", "_").replace(" ", "")
        email = f"{SHADOW_EMAIL_PREFIX}{clean_id}@{SHADOW_EMAIL_DOMAIN}".lower()
        
        user = db.scalar(select(User).where(User.email == email))
        if user is not None:
            if display_name and user.display_name != display_name:
                user.display_name = display_name
                db.commit()
                db.refresh(user)
            return user
            
        temp_password = secrets.token_urlsafe(16)
        user = User(
            id=str(uuid4()),
            email=email,
            display_name=display_name or f"Du khách Zalo ({clean_id[:6]})",
            password_hash=hash_password(temp_password),
            role="traveler",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def pick_dynamic_experiences(
        self,
        db: Session,
        intent_summary: str = "",
        budget_vnd: int = 500000,
        group_size: int = 2
    ) -> List[Experience]:
        """
        Dynamically pick 4 high-quality experiences from the real database (local_explorer.db)
        matching user intent, category distribution, and realistic day schedule:
          - Stop 1: Cafe / breakfast (category: cafe or an-uong)
          - Stop 2: Culture / museum / heritage (category: tham-quan)
          - Stop 3: Culinary / lunch specialties (category: an-uong)
          - Stop 4: Check-in / sightseeing / entertainment (category: tham-quan, giai-tri)
        """
        all_exps = list(db.scalars(
            select(Experience)
            .join(POI)
            .options(joinedload(Experience.poi), selectinload(Experience.slots))
        ).unique())

        if not all_exps:
            return []

        text_lower = (intent_summary or "").lower()

        cafes = [e for e in all_exps if e.poi and e.poi.category == 'cafe']
        sights = [e for e in all_exps if e.poi and e.poi.category == 'tham-quan']
        foods = [e for e in all_exps if e.poi and e.poi.category == 'an-uong']
        afternoons = [e for e in all_exps if e.poi and e.poi.category in ('giai-tri', 'tham-quan')]

        # Fallbacks if any category is sparse
        if not cafes:
            cafes = all_exps[:5]
        if not sights:
            sights = all_exps[5:10]
        if not foods:
            foods = all_exps[10:15]
        if not afternoons:
            afternoons = all_exps[15:20]

        def rank_candidates(pool: List[Experience], text: str) -> List[Experience]:
            tokens = [t for t in re.split(r'[,.\s]+', text) if len(t) >= 3]
            scored = []
            for e in pool:
                name_norm = e.name.lower()
                poi_norm = e.poi.name.lower() if e.poi else ""
                intent_tags_str = " ".join(e.intent_tags or []).lower()
                score = 0
                for t in tokens:
                    if t in name_norm or t in poi_norm:
                        score += 3
                    elif t in intent_tags_str:
                        score += 1
                scored.append((score, e))
            
            # Sort by keyword match score descending
            scored.sort(key=lambda x: x[0], reverse=True)
            top_matches = [item[1] for item in scored if item[0] > 0]
            if top_matches:
                return top_matches
            # If no keyword matches, shuffle slightly to provide variety across bookings
            return random.sample(pool, min(len(pool), 6))

        # 1. Pick Cafe
        ranked_cafes = rank_candidates(cafes, text_lower)
        s1 = ranked_cafes[0] if ranked_cafes else cafes[0]

        # 2. Pick Sight
        ranked_sights = rank_candidates(sights, text_lower)
        s2_candidates = [e for e in ranked_sights if e.id != s1.id]
        s2 = s2_candidates[0] if s2_candidates else (sights[0] if sights[0].id != s1.id else sights[1])

        # 3. Pick Food
        ranked_foods = rank_candidates(foods, text_lower)
        s3_candidates = [e for e in ranked_foods if e.id not in (s1.id, s2.id)]
        s3 = s3_candidates[0] if s3_candidates else foods[0]

        # 4. Pick Afternoon
        ranked_afternoons = rank_candidates(afternoons, text_lower)
        s4_candidates = [e for e in ranked_afternoons if e.id not in (s1.id, s2.id, s3.id)]
        s4 = s4_candidates[0] if s4_candidates else afternoons[0]

        return [s1, s2, s3, s4]

    def generate_ticket(
        self,
        chat_id: str,
        customer_name: str,
        intent_summary: str = "Khám phá Sài Gòn",
        budget_vnd: int = 500000,
        group_size: int = 2,
    ) -> Dict[str, Any]:
        """
        Generate a legacy ticket. Disabled whenever REAL_DATA_ONLY is enabled.
        """
        if settings.real_data_only:
            raise RuntimeError(
                "Legacy ticket generation is disabled in REAL_DATA_ONLY mode. "
                "Use the itinerary planner and booking APIs instead."
            )
        db = self._get_db()
        should_close = self._db is None
        try:
            shadow_user = self.get_or_create_shadow_user(db, chat_id, customer_name)
            
            # Select 4 dynamic experiences from actual web database matching user intent
            experiences = self.pick_dynamic_experiences(
                db=db,
                intent_summary=intent_summary,
                budget_vnd=budget_vnd,
                group_size=group_size
            )
            
            if len(experiences) < 4:
                # Ultimate fallback from database
                more_exps = db.scalars(
                    select(Experience)
                    .options(joinedload(Experience.poi))
                    .where(Experience.id.not_in([e.id for e in experiences]))
                    .limit(4 - len(experiences))
                ).all()
                experiences.extend(more_exps)

            # Generate fresh, dedicated ticket code and ID for this confirmed schedule
            itinerary_id = str(uuid4())
            # The short code is only printed on the ticket; the share token is the read credential, so it must
            # be unguessable, and ownership moves only through the separate single-use claim token below.
            ticket_code = f"SG-PASS-{secrets.token_hex(3).upper()}"
            token = secrets.token_urlsafe(32)
            
            now = datetime.now(timezone.utc)
            start_date = now + timedelta(days=1)
            trip_start = start_date.replace(hour=8, minute=30, second=0, microsecond=0)
            trip_end = start_date.replace(hour=17, minute=30, second=0, microsecond=0)
            
            total_calculated_cost = 0

            itinerary = Itinerary(
                id=itinerary_id,
                user_id=shadow_user.id,
                share_token=token,
                city="TP. Hồ Chí Minh",
                planned_date=trip_start.date(),
                start_time=trip_start,
                return_deadline=trip_end,
                group_size=group_size,
                budget_vnd=budget_vnd,
                travel_mode="driving",
                status="confirmed",
                start_at=trip_start,
                end_at=trip_end,
                estimated_cost_vnd=budget_vnd,
                constraints={
                    "transport_mode": "driving",
                    "intent": intent_summary,
                    "customer_name": customer_name,
                    "chat_id": str(chat_id),
                    "ticket_code": ticket_code,
                },
                data_mode="simulated"
            )
            db.add(itinerary)
            db.flush()
            
            # Add stops matching the schedule
            for idx, exp in enumerate(experiences[:4], start=1):
                timing = SCHEDULE_TIMELINE[idx - 1]
                stop_start = trip_start.replace(hour=timing["hour_start"], minute=timing["minute_start"])
                duration = timing["duration"]
                stop_end = stop_start + timedelta(minutes=duration)
                
                # Base cost from real experience price
                cost_per_person = exp.price_vnd if exp.price_vnd > 0 else (65000 if idx == 1 else (150000 if idx == 3 else 0))
                stop_total_cost = cost_per_person * group_size
                total_calculated_cost += stop_total_cost
                
                # Find an available slot for this experience
                slot = db.scalar(select(ExperienceSlot).where(ExperienceSlot.experience_id == exp.id).limit(1))
                slot_id = slot.id if slot else str(uuid4())
                
                stop = ItineraryStop(
                    id=str(uuid4()),
                    itinerary_id=itinerary.id,
                    experience_id=exp.id,
                    slot_id=slot_id,
                    poi_id=exp.poi_id,
                    position=idx,
                    stop_order=idx,
                    arrival_at=stop_start,
                    departure_at=stop_end,
                    start_at=stop_start,
                    end_at=stop_end,
                    activity_duration_min=duration,
                    cost_vnd=cost_per_person,
                    status="planned",
                    is_locked=False,
                )
                db.add(stop)
                
            itinerary.estimated_cost_vnd = total_calculated_cost if total_calculated_cost > 0 else budget_vnd
            claim_token = issue_claim_token(db, itinerary.id)
            db.commit()
            
            return {
                "ticket_code": ticket_code,
                "share_token": token,
                "itinerary_id": itinerary.id,
                "url_prod": f"{PROD_DOMAIN}/shared/{token}",
                "url_local": f"{LOCAL_DOMAIN}/shared/{token}",
                # Send only to the traveller who booked: whoever opens it first can attach the trip to an account.
                "claim_url_prod": f"{PROD_DOMAIN}/shared/{token}?claim={claim_token}",
                "claim_url_local": f"{LOCAL_DOMAIN}/shared/{token}?claim={claim_token}",
                "estimated_cost_vnd": itinerary.estimated_cost_vnd,
                "stops_count": len(experiences[:4]),
                "customer_name": customer_name,
                "is_existing": False,
                "stops": [
                    {
                        "position": i + 1,
                        "name": exp.name,
                        "poi_name": exp.poi.name if exp.poi else exp.name,
                        "category": exp.poi.category if exp.poi else "tham-quan",
                        "address": exp.poi.address if exp.poi else "TP. Hồ Chí Minh",
                        "cost_vnd": exp.price_vnd,
                    }
                    for i, exp in enumerate(experiences[:4])
                ]
            }
        finally:
            if should_close:
                db.close()


ticket_service = TicketService()
