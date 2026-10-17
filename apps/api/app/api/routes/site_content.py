"""Traveler-web content managed in the admin portal: home banners, articles and place collections."""

import re
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.guards import public, require_user
from app.api.permissions import P
from app.models.entities import AuditLog, POI, SiteArticle, SiteBanner, SiteCollection, User
from app.schemas.portal import ArticlePayload, BannerPayload, CollectionPayload

router = APIRouter(prefix="/api", tags=["site content"])
PUBLIC_PLACE_STATUSES = ("verified", "simulated")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def _audit(db: Session, actor: User, action: str, target_type: str, target_id: str) -> None:
    db.add(AuditLog(id=str(uuid4()), actor_id=actor.id, action=action, target_type=target_type, target_id=target_id, details={}, created_at=_now()))


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.replace("đ", "d").replace("Đ", "D"))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:200] or "bai-viet"


def _not_found(kind: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": f"{kind.upper()}_NOT_FOUND", "message": f"{kind.capitalize()} not found."})


def _get(db: Session, model, item_id: str, kind: str):
    item = db.get(model, item_id)
    if item is None:
        raise _not_found(kind)
    return item


def banner_view(item: SiteBanner) -> dict:
    return {"id": item.id, "title": item.title, "subtitle": item.subtitle, "image_url": item.image_url, "link_url": item.link_url,
            "is_active": item.is_active, "sort_order": item.sort_order, "starts_at": item.starts_at, "ends_at": item.ends_at, "updated_at": item.updated_at}


def article_view(item: SiteArticle, *, with_body: bool = True) -> dict:
    data = {"id": item.id, "title": item.title, "slug": item.slug, "excerpt": item.excerpt, "cover_url": item.cover_url,
            "category": item.category, "status": item.status, "published_at": item.published_at, "updated_at": item.updated_at}
    return {**data, "body": item.body} if with_body else data


def collection_view(item: SiteCollection, places: dict[str, POI] | None = None) -> dict:
    data = {"id": item.id, "title": item.title, "description": item.description, "place_ids": item.place_ids or [],
            "is_active": item.is_active, "sort_order": item.sort_order, "updated_at": item.updated_at}
    if places is not None:
        data["places"] = [{"id": p.id, "name": p.name, "district": p.district, "category": p.category,
                           "image_url": (p.image_urls or [None])[0], "is_landmark": p.is_landmark}
                          for pid in item.place_ids or [] if (p := places.get(pid))]
    return data


# ---------------- Admin: banners ----------------

@router.get("/admin/content/banners")
def list_banners(actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    return [banner_view(b) for b in db.scalars(select(SiteBanner).order_by(SiteBanner.sort_order, SiteBanner.created_at))]


@router.post("/admin/content/banners", status_code=201)
def create_banner(payload: BannerPayload, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    banner = SiteBanner(id=str(uuid4()), **payload.model_dump())
    db.add(banner)
    _audit(db, actor, "banner.created", "banner", banner.id)
    db.commit()
    return banner_view(banner)


@router.put("/admin/content/banners/{banner_id}")
def update_banner(banner_id: str, payload: BannerPayload, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    banner = _get(db, SiteBanner, banner_id, "banner")
    for key, value in payload.model_dump().items():
        setattr(banner, key, value)
    _audit(db, actor, "banner.updated", "banner", banner.id)
    db.commit()
    return banner_view(banner)


@router.delete("/admin/content/banners/{banner_id}", status_code=204)
def delete_banner(banner_id: str, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    banner = _get(db, SiteBanner, banner_id, "banner")
    db.delete(banner)
    _audit(db, actor, "banner.deleted", "banner", banner_id)
    db.commit()


# ---------------- Admin: articles ----------------

def _unique_slug(db: Session, wanted: str, article_id: str | None) -> str:
    slug, n = wanted, 2
    while (existing := db.scalar(select(SiteArticle.id).where(SiteArticle.slug == slug))) and existing != article_id:
        slug, n = f"{wanted}-{n}", n + 1
    return slug


def _apply_article(db: Session, article: SiteArticle, payload: ArticlePayload) -> None:
    for key, value in payload.model_dump(exclude={"slug"}).items():
        setattr(article, key, value)
    article.slug = _unique_slug(db, payload.slug or slugify(payload.title), article.id)
    if payload.status == "published" and article.published_at is None:
        article.published_at = _now()


@router.get("/admin/content/articles")
def list_articles(actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    return [article_view(a, with_body=False) for a in db.scalars(select(SiteArticle).order_by(SiteArticle.updated_at.desc()))]


@router.get("/admin/content/articles/{article_id}")
def get_article(article_id: str, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    return article_view(_get(db, SiteArticle, article_id, "article"))


@router.post("/admin/content/articles", status_code=201)
def create_article(payload: ArticlePayload, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    article = SiteArticle(id=str(uuid4()), author_id=actor.id)
    _apply_article(db, article, payload)
    db.add(article)
    _audit(db, actor, "article.created", "article", article.id)
    db.commit()
    return article_view(article)


@router.put("/admin/content/articles/{article_id}")
def update_article(article_id: str, payload: ArticlePayload, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    article = _get(db, SiteArticle, article_id, "article")
    _apply_article(db, article, payload)
    _audit(db, actor, "article.updated", "article", article.id)
    db.commit()
    return article_view(article)


@router.delete("/admin/content/articles/{article_id}", status_code=204)
def delete_article(article_id: str, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    article = _get(db, SiteArticle, article_id, "article")
    db.delete(article)
    _audit(db, actor, "article.deleted", "article", article_id)
    db.commit()


# ---------------- Admin: collections ----------------

def _check_places(db: Session, place_ids: list[str]) -> list[str]:
    ids = list(dict.fromkeys(place_ids))
    found = set(db.scalars(select(POI.id).where(POI.id.in_(ids)))) if ids else set()
    if missing := [pid for pid in ids if pid not in found]:
        raise HTTPException(status_code=422, detail={"code": "PLACE_NOT_FOUND", "message": f"Unknown places: {', '.join(missing)}"})
    return ids


@router.get("/admin/content/collections")
def list_collections(actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    return [collection_view(c) for c in db.scalars(select(SiteCollection).order_by(SiteCollection.sort_order, SiteCollection.created_at))]


@router.post("/admin/content/collections", status_code=201)
def create_collection(payload: CollectionPayload, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    collection = SiteCollection(id=str(uuid4()), **{**payload.model_dump(), "place_ids": _check_places(db, payload.place_ids)})
    db.add(collection)
    _audit(db, actor, "collection.created", "collection", collection.id)
    db.commit()
    return collection_view(collection)


@router.put("/admin/content/collections/{collection_id}")
def update_collection(collection_id: str, payload: CollectionPayload, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    collection = _get(db, SiteCollection, collection_id, "collection")
    for key, value in {**payload.model_dump(), "place_ids": _check_places(db, payload.place_ids)}.items():
        setattr(collection, key, value)
    _audit(db, actor, "collection.updated", "collection", collection.id)
    db.commit()
    return collection_view(collection)


@router.delete("/admin/content/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: str, actor: User = Depends(require_user(P.ADMIN_CONTENT)), db: Session = Depends(get_db)):
    collection = _get(db, SiteCollection, collection_id, "collection")
    db.delete(collection)
    _audit(db, actor, "collection.deleted", "collection", collection_id)
    db.commit()


# ---------------- Public (traveler web) ----------------

@router.get("/content/home", dependencies=[Depends(public("published home-page content"))])
def home_content(db: Session = Depends(get_db)):
    """Everything the traveler home page needs in one call: live banners, active collections, latest articles."""
    now = _now()
    banners = [b for b in db.scalars(select(SiteBanner).where(SiteBanner.is_active.is_(True)).order_by(SiteBanner.sort_order, SiteBanner.created_at))
               if (b.starts_at is None or _aware(b.starts_at) <= now) and (b.ends_at is None or _aware(b.ends_at) > now)]
    collections = db.scalars(select(SiteCollection).where(SiteCollection.is_active.is_(True)).order_by(SiteCollection.sort_order, SiteCollection.created_at)).all()
    place_ids = {pid for c in collections for pid in c.place_ids or []}
    # Only places travelers may see; hidden or draft ones silently drop out of a collection.
    places = {p.id: p for p in db.scalars(select(POI).where(POI.id.in_(place_ids), POI.verification_status.in_(PUBLIC_PLACE_STATUSES)))} if place_ids else {}
    articles = db.scalars(select(SiteArticle).where(SiteArticle.status == "published").order_by(SiteArticle.published_at.desc()).limit(6)).all()
    return {
        "banners": [banner_view(b) for b in banners],
        "collections": [view for c in collections if (view := collection_view(c, places))["places"]],
        "articles": [article_view(a, with_body=False) for a in articles],
    }


@router.get("/content/articles", dependencies=[Depends(public("published articles"))])
def published_articles(db: Session = Depends(get_db), category: str | None = Query(default=None, max_length=60),
                       q: str | None = Query(default=None, max_length=120), limit: int = Query(default=24, ge=1, le=100)):
    query = select(SiteArticle).where(SiteArticle.status == "published")
    if category:
        query = query.where(SiteArticle.category == category)
    if q and q.strip():
        query = query.where(or_(SiteArticle.title.ilike(f"%{q.strip()}%"), SiteArticle.excerpt.ilike(f"%{q.strip()}%")))
    return [article_view(a, with_body=False) for a in db.scalars(query.order_by(SiteArticle.published_at.desc()).limit(limit))]


@router.get("/content/articles/{slug}", dependencies=[Depends(public("published article"))])
def published_article(slug: str, db: Session = Depends(get_db)):
    article = db.scalar(select(SiteArticle).where(SiteArticle.slug == slug, SiteArticle.status == "published"))
    if article is None:
        raise _not_found("article")
    return article_view(article)
