"""Deterministic tag/category baseline used by the ranking benchmark.

This is a reference rule, not a statement about real user preference. The weak
dataset's grades were produced from an intent/category rule, so a strong score
here measures rule imitation only.
"""

from __future__ import annotations

from typing import Any

from app.services.ranker_features import intent_families, parse_tags


_RELATED: dict[str, set[str]] = {
    "food": {"coffee"},
    "coffee": {"food"},
    "culture": {"art", "sightseeing"},
    "art": {"culture"},
    "nature": {"sightseeing"},
    "entertainment": {"sport"},
    "relaxation": {"nature", "sport"},
}


def rule_baseline_score(query: dict[str, Any], candidate: dict[str, Any]) -> float:
    """Score a candidate from tags only; never read target/ID/rationale fields."""
    wanted = intent_families(parse_tags(query.get("user_intent_tags")))
    offered = intent_families(parse_tags(candidate.get("candidate_tags")))
    if wanted & offered:
        return 3.0
    if any(_RELATED.get(family, set()) & offered for family in wanted):
        return 2.0
    return 0.0
