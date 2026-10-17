from datetime import datetime, timezone
from typing import Any, Protocol, Sequence

def as_aware(value: datetime) -> datetime:
    # SQLAlchemy's SQLite test/dev backend strips tzinfo from DateTime(timezone=True)
    # values. Persisted naive timestamps follow the application's UTC storage convention.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PlannerEngine(Protocol):
    """Replaceable decision engine; candidates have already passed hard constraints."""

    def plan(self, candidates: Sequence[dict[str, Any]]) -> dict[str, Any] | None: ...


class HeuristicPlanner:
    """At each step, schedule the earliest feasible slot and rank ties by intent fit."""

    def plan(self, candidates: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return None
        locked = [item for item in candidates if item["locked"]]
        if locked:
            return min(locked, key=lambda item: as_aware(item["slot"].start_at))
        earliest: datetime = min(as_aware(item["slot"].start_at) for item in candidates)
        same_time = [item for item in candidates if as_aware(item["slot"].start_at) == earliest]
        return max(same_time, key=lambda item: (item["score"], -item["cost"]))


class SuggestionPlanner(HeuristicPlanner):
    """Prioritize already-feasible candidates; never relax trip constraints."""

    def __init__(self, style: str):
        self.style = style

    def plan(self, candidates):
        if not candidates or self.style == 'balanced':
            return super().plan(candidates)
        locked = [item for item in candidates if item['locked']]
        if locked:
            return min(locked, key=lambda item: as_aware(item['slot'].start_at))
        def priority(item):
            early = as_aware(item['slot'].start_at)
            if self.style == 'budget':
                return (item['cost'], early, -item['score'])
            if self.style == 'nearby':
                return (item['travel'] + item['return_travel'], early, -item['score'])
            if self.style == 'relaxed':
                return (item['experience'].duration_min + item['travel'], early, -item['score'])
            return (-item['score'], early, item['cost'])
        return min(candidates, key=priority)
