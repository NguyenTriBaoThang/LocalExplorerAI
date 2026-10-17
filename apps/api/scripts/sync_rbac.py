"""Insert permissions that exist in code but not yet in the database, granting each to its default roles.

    python -m scripts.sync_rbac

Run it after deploying code that adds a permission. Grants an administrator removed on purpose are never restored.
"""

from app.db.session import SessionLocal
from app.services.rbac_service import sync_catalog


def main() -> None:
    with SessionLocal() as db:
        created = sync_catalog(db)
    print(f"added {len(created)} permission(s)" + (": " + ", ".join(created) if created else ""))


if __name__ == "__main__":
    main()
