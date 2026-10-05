"""Page-view collection and the traffic reports shown in the portal.

Privacy: the browser sends a random id it keeps in local storage; only an HMAC of it is stored, together with the
path, referrer host and a coarse device class. No IP address, user agent or query string is kept.
"""

import hashlib
import hmac
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_entities import AuthEvent
from app.models.entities import Booking, Experience, ExperienceReview, PageView, POI, SiteArticle, User

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
BOT_MARKERS = ("bot", "crawler", "spider", "slurp", "headless", "lighthouse", "preview")
SEARCH_HOSTS = ("google.", "bing.", "coccoc.", "yahoo.", "duckduckgo.", "yandex.", "baidu.")
SOCIAL_HOSTS = ("facebook.", "fb.", "instagram.", "tiktok.", "zalo.", "youtube.", "youtu.be", "twitter.", "x.com", "threads.", "linkedin.", "reddit.")
PAGE_TITLES = {
    "/": "Trang chủ", "/explore": "Khám phá", "/planner": "Lập lịch trình", "/chat": "AI Concierge", "/map-3d": "Bản đồ 3D",
    "/about": "Giới thiệu", "/provider": "Đối tác", "/compare": "So sánh lịch trình", "/profile": "Tài khoản", "/guides": "Cẩm nang",
}


def _key() -> bytes:
    # Pseudonymisation key. Without APP_SIGNING_SECRET the ids are still hashed, just with a well-known key.
    return (settings.app_signing_secret or "local-explorer-analytics").encode()


def pseudonymize(value: str) -> str:
    return hmac.new(_key(), value.encode(), hashlib.sha256).hexdigest()


def is_bot(user_agent: str | None) -> bool:
    agent = (user_agent or "").lower()
    return not agent or any(marker in agent for marker in BOT_MARKERS)


def device_class(user_agent: str | None) -> str:
    agent = (user_agent or "").lower()
    if "ipad" in agent or "tablet" in agent or ("android" in agent and "mobile" not in agent):
        return "tablet"
    if "mobile" in agent or "iphone" in agent or "android" in agent:
        return "mobile"
    return "desktop"


def referrer_host(referrer: str | None, own_host: str | None) -> str | None:
    if not referrer:
        return None
    try:
        host = (urlsplit(referrer).hostname or "").lower()
    except ValueError:
        return None
    if not host or (own_host and host == own_host.split(":")[0].lower()):
        return None
    return host[:200]


def source_class(host: str | None) -> str:
    if not host:
        return "Trực tiếp"
    if any(marker in host for marker in SEARCH_HOSTS):
        return "Tìm kiếm"
    if any(marker in host for marker in SOCIAL_HOSTS):
        return "Mạng xã hội"
    return "Giới thiệu"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _window(days: int) -> tuple[list, datetime, datetime]:
    """Local calendar days ending today, the window start and the start of the equally long previous window."""
    today = datetime.now(LOCAL_TZ).date()
    dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    start = datetime.combine(dates[0], datetime.min.time(), LOCAL_TZ)
    return dates, start, start - timedelta(days=days)


def _day(value: datetime):
    return _aware(value).astimezone(LOCAL_TZ).date()


def _change(current: float, previous: float) -> float | None:
    return None if previous == 0 else round((current - previous) / previous * 100, 1)


def admin_report(db: Session, days: int) -> dict:
    dates, start, previous_start = _window(days)
    views = db.scalars(select(PageView).where(PageView.occurred_at >= previous_start)).all()
    current = [v for v in views if _aware(v.occurred_at) >= start]
    previous = [v for v in views if _aware(v.occurred_at) < start]

    users = db.scalars(select(User.created_at).where(User.created_at >= previous_start)).all()
    logins = db.scalars(select(AuthEvent.created_at).where(AuthEvent.created_at >= start, AuthEvent.event_type == "login", AuthEvent.outcome == "success")).all()
    bookings = db.scalars(select(Booking.created_at).where(Booking.created_at >= previous_start)).all()

    per_day: dict = defaultdict(lambda: {"visitors": set(), "pageviews": 0})
    for view in current:
        bucket = per_day[_day(view.occurred_at)]
        bucket["visitors"].add(view.visitor_hash)
        bucket["pageviews"] += 1
    count_by_day = lambda stamps: Counter(_day(stamp) for stamp in stamps if _aware(stamp) >= start)  # noqa: E731
    new_users, login_days, booking_days = count_by_day(users), count_by_day(logins), count_by_day(bookings)
    series = [{
        "date": day.isoformat(), "label": f"{day.day}/{day.month}",
        "visitors": len(per_day[day]["visitors"]) if day in per_day else 0,
        "pageviews": per_day[day]["pageviews"] if day in per_day else 0,
        "new_users": new_users.get(day, 0), "logins": login_days.get(day, 0), "bookings": booking_days.get(day, 0),
    } for day in dates]

    sessions: dict[str, list[datetime]] = defaultdict(list)
    for view in current:
        sessions[view.session_hash].append(_aware(view.occurred_at))
    durations = [(max(stamps) - min(stamps)).total_seconds() for stamps in sessions.values()]

    place_counts = Counter(v.entity_id for v in current if v.entity_type == "poi" and v.entity_id)
    places = {p.id: p for p in db.scalars(select(POI).where(POI.id.in_(list(place_counts)))).all()} if place_counts else {}
    totals = {
        "visitors": len({v.visitor_hash for v in current}), "pageviews": len(current),
        "new_users": sum(1 for stamp in users if _aware(stamp) >= start),
        "bookings": sum(1 for stamp in bookings if _aware(stamp) >= start),
        "avg_session_seconds": round(sum(durations) / len(durations)) if durations else 0,
        "sessions": len(sessions),
    }
    return {
        "days": days,
        "totals": totals,
        "change": {
            "visitors": _change(totals["visitors"], len({v.visitor_hash for v in previous})),
            "pageviews": _change(totals["pageviews"], len(previous)),
            "new_users": _change(totals["new_users"], sum(1 for stamp in users if _aware(stamp) < start)),
            "bookings": _change(totals["bookings"], sum(1 for stamp in bookings if _aware(stamp) < start)),
        },
        "series": series,
        "top_pages": _page_titles(db, Counter(v.path for v in current).most_common(8)),
        "top_places": [{"id": place_id, "name": places[place_id].name, "district": places[place_id].district or "", "views": count}
                       for place_id, count in place_counts.most_common(8) if place_id in places],
        "devices": [{"label": label, "value": Counter(v.device for v in current).get(key, 0)}
                    for key, label in (("mobile", "Di động"), ("desktop", "Máy tính"), ("tablet", "Máy tính bảng"))],
        "sources": [{"label": label, "value": count} for label, count in Counter(source_class(v.referrer_host) for v in current).most_common()],
        "hours": [Counter(_aware(v.occurred_at).astimezone(LOCAL_TZ).hour for v in current).get(hour, 0) for hour in range(24)],
    }


def _page_titles(db: Session, ranked: list[tuple[str, int]]) -> list[dict]:
    """Readable titles for the most viewed paths: fixed pages by name, detail pages by the place or article they show."""
    place_ids = [path.split("/")[2] for path, _ in ranked if path.startswith("/places/") and path.count("/") == 2]
    slugs = [path.split("/")[2] for path, _ in ranked if path.startswith("/guides/") and path.count("/") == 2]
    places = dict(db.execute(select(POI.id, POI.name).where(POI.id.in_(place_ids))).all()) if place_ids else {}
    articles = dict(db.execute(select(SiteArticle.slug, SiteArticle.title).where(SiteArticle.slug.in_(slugs))).all()) if slugs else {}

    def title(path: str) -> str:
        key = path.split("/")[2] if path.count("/") == 2 else ""
        if path.startswith("/places/") and key in places:
            return f"Địa điểm · {places[key]}"
        if path.startswith("/guides/") and key in articles:
            return f"Cẩm nang · {articles[key]}"
        return PAGE_TITLES.get(path, path)

    return [{"path": path, "title": title(path), "views": count} for path, count in ranked]


def provider_report(db: Session, provider_id: str, days: int) -> dict:
    dates, start, _ = _window(days)
    experience_ids = db.scalars(select(Experience.id).where(Experience.provider_id == provider_id)).all()
    views = db.scalars(select(PageView.occurred_at).where(
        PageView.entity_type == "experience", PageView.entity_id.in_(experience_ids), PageView.occurred_at >= start,
    )).all() if experience_ids else []
    requests = db.scalars(select(Booking.created_at).where(Booking.provider_id == provider_id, Booking.created_at >= start)).all()
    ratings = db.scalars(select(ExperienceReview.rating).where(ExperienceReview.provider_id == provider_id, ExperienceReview.status == "published")).all()
    view_days, request_days = Counter(_day(stamp) for stamp in views), Counter(_day(stamp) for stamp in requests)
    return {
        "series": [{"label": f"{day.day}/{day.month}", "views": view_days.get(day, 0), "booking_requests": request_days.get(day, 0)} for day in dates],
        "totals": {
            "views": len(views), "booking_requests": len(requests),
            "conversion": round(len(requests) / len(views) * 100, 1) if views else 0.0,
            "rating": round(sum(ratings) / len(ratings), 1) if ratings else None, "reviews": len(ratings),
        },
    }
