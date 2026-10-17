"""Rules shared by experience reviews and place reviews."""

from __future__ import annotations

import re

from fastapi import HTTPException

PRIOR_MEAN = 4.0      # what an average rated place is assumed to be worth before it has many ratings
PRIOR_WEIGHT = 5      # how many ratings that assumption counts for


def author_label(name: str | None) -> str:
    """Public reviews show a first name and initial only."""
    parts = (name or "").split()
    if not parts:
        return "Du khách"
    return parts[-1] if len(parts) == 1 else f"{parts[-1]} {parts[0][0]}."


def ranking_score(average: float | None, count: int) -> float:
    """Average pulled towards the prior by the number of ratings, so one 5-star review does not outrank forty 4.8s.

    Used only to order things; the page still shows the plain average and the count.
    """
    if not count or average is None:
        return 0.0
    return (PRIOR_WEIGHT * PRIOR_MEAN + average * count) / (PRIOR_WEIGHT + count)


_LINK = re.compile(r"(https?://|www\.)", re.IGNORECASE)


def check_comment(text: str) -> str:
    """Trim and reject the obvious spam shape (links). Anything else is left to moderators."""
    text = (text or "").strip()
    if len(_LINK.findall(text)) > 0:
        raise HTTPException(status_code=422, detail={"code": "REVIEW_REJECTED", "message": "Reviews cannot contain links."})
    return text
