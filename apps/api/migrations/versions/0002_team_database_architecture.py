"""Complete the team's Local Explorer database architecture.

Revision ID: 0002_team_database_architecture
Revises: 0001_initial
"""

import re
import unicodedata

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.db.base import Base
from app.models import entities  # noqa: F401

revision = "0002_team_database_architecture"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


# (table, column) pairs created by the live models but introduced by a later revision; kept in step with 0003+.
LATER_COLUMNS: list[tuple[str, str]] = [
    ("intent_similarities", "can_substitute_purpose"),
    ("intent_similarities", "prompt_version"),
]


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "provider"


def _replace_json_array_column(table: str, column: str) -> None:
    """Convert a JSON list column into PostgreSQL text[] without dropping values."""
    connection = op.get_bind()
    legacy = f"{column}_json_legacy"
    op.alter_column(table, column, new_column_name=legacy)
    op.add_column(table, sa.Column(column, postgresql.ARRAY(sa.Text()), nullable=True))
    rows = connection.execute(sa.text(f"SELECT id, {legacy} FROM {table}")).all()
    for row_id, values in rows:
        if isinstance(values, str):
            import json

            values = json.loads(values)
        connection.execute(
            sa.text(f"UPDATE {table} SET {column} = :values WHERE id = :row_id"),
            {"values": list(values or []), "row_id": row_id},
        )
    op.alter_column(table, column, nullable=False, server_default=sa.text("'{}'::text[]"))
    op.drop_column(table, legacy)


def _normalize_poi_geometry() -> None:
    op.execute("ALTER TABLE pois ALTER COLUMN geom TYPE geometry(Point, 4326) USING geom::geometry")
    op.execute("""
        UPDATE pois
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE geom IS NULL
    """)
    op.execute("ALTER TABLE pois ALTER COLUMN geom SET NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pois_geom ON pois USING GIST (geom)")


def upgrade() -> None:
    # Compatibility for databases created by the pre-release dynamic 0001 revision,
    # which could have created the current tables before this revision existed.
    inspector = sa.inspect(op.get_bind())
    if "slug" in {column["name"] for column in inspector.get_columns("providers")} and "events" in inspector.get_table_names():
        _normalize_poi_geometry()
        return

    # Add new columns nullable first, then backfill, so populated databases upgrade safely.
    op.add_column("providers", sa.Column("slug", sa.String(180), nullable=True))
    op.add_column("providers", sa.Column("address", sa.String(300), nullable=False, server_default=""))
    op.add_column("providers", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("providers", sa.Column("verification_status", sa.String(32), nullable=False, server_default="mock"))
    op.add_column("providers", sa.Column("portal_access_key", sa.String(128), nullable=True))

    connection = op.get_bind()
    used_slugs: set[str] = set()
    for row_id, name in connection.execute(sa.text("SELECT id, name FROM providers ORDER BY id")):
        base = _slug(name)
        slug = base
        suffix = 2
        while slug in used_slugs:
            slug = f"{base}-{suffix}"
            suffix += 1
        used_slugs.add(slug)
        connection.execute(sa.text("UPDATE providers SET slug = :slug WHERE id = :id"), {"slug": slug, "id": row_id})
    op.alter_column("providers", "slug", nullable=False)
    op.create_unique_constraint("uq_providers_slug", "providers", ["slug"])
    op.execute("""
        UPDATE providers SET
            is_active = lower(status) NOT IN ('inactive', 'disabled'),
            verification_status = 'mock'
    """)

    op.add_column("pois", sa.Column("district", sa.String(120), nullable=True))
    op.add_column("pois", sa.Column("source_attribution", sa.Text(), nullable=True))
    op.add_column("pois", sa.Column("is_in_pilot_polygon", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("pois", sa.Column("image_urls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.create_index("ix_pois_district", "pois", ["district"])

    op.add_column("experiences", sa.Column("title", sa.String(180), nullable=True))
    op.add_column("experiences", sa.Column("is_hands_on", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("experiences", sa.Column("is_indoor", sa.Boolean(), nullable=False, server_default=sa.true()))
    connection.execute(sa.text("UPDATE experiences SET title = name, is_indoor = indoor"))
    for row_id, tags in connection.execute(sa.text("SELECT id, intent_tags FROM experiences")):
        if isinstance(tags, str):
            import json

            tags = json.loads(tags)
        connection.execute(
            sa.text("UPDATE experiences SET is_hands_on = :hands_on WHERE id = :id"),
            {"hands_on": "hands_on" in (tags or []), "id": row_id},
        )
    op.alter_column("experiences", "title", nullable=False)
    _replace_json_array_column("experiences", "intent_tags")
    op.alter_column("experiences", "price_vnd", type_=sa.BigInteger(), postgresql_using="price_vnd::bigint")
    op.create_check_constraint(
        "ck_experience_slots_status", "experience_slots",
        "status IN ('open', 'full', 'cancelled', 'available', 'unavailable', 'tentative')",
    )

    op.add_column("itineraries", sa.Column("user_session_id", sa.String(128), nullable=True))
    op.add_column("itineraries", sa.Column("city", sa.String(100), nullable=False, server_default="Ho Chi Minh City"))
    op.add_column("itineraries", sa.Column("planned_date", sa.Date(), nullable=True))
    op.add_column("itineraries", sa.Column("start_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("itineraries", sa.Column("return_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("itineraries", sa.Column("travel_mode", sa.String(24), nullable=False, server_default="driving"))
    op.add_column("itineraries", sa.Column("target_intents", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("itineraries", sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"))
    connection.execute(sa.text("""
        UPDATE itineraries SET
            planned_date = start_at::date,
            start_time = start_at,
            return_deadline = end_at,
            current_version = version,
            target_intents = COALESCE((constraints->'intent_weights')::jsonb, '{}'::jsonb)
    """))
    op.alter_column("itineraries", "budget_vnd", type_=sa.BigInteger(), postgresql_using="budget_vnd::bigint")
    op.alter_column("itineraries", "estimated_cost_vnd", type_=sa.BigInteger(), postgresql_using="estimated_cost_vnd::bigint")
    op.create_index("ix_itineraries_user_session_id", "itineraries", ["user_session_id"])

    op.add_column("itinerary_stops", sa.Column("poi_id", sa.String(36), nullable=True))
    op.add_column("itinerary_stops", sa.Column("stop_order", sa.Integer(), nullable=True))
    op.add_column("itinerary_stops", sa.Column("departure_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("itinerary_stops", sa.Column("wait_duration_min", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("itinerary_stops", sa.Column("activity_duration_min", sa.Integer(), nullable=True))
    op.add_column("itinerary_stops", sa.Column("status", sa.String(24), nullable=False, server_default="planned"))
    op.add_column("itinerary_stops", sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()))
    connection.execute(sa.text("""
        UPDATE itinerary_stops AS s SET
            poi_id = e.poi_id,
            stop_order = s.position,
            departure_at = s.end_at,
            activity_duration_min = GREATEST(FLOOR(EXTRACT(EPOCH FROM (s.end_at - s.start_at)) / 60), 0)::integer,
            is_locked = s.locked
        FROM experiences AS e WHERE e.id = s.experience_id
    """))
    op.alter_column("itinerary_stops", "poi_id", nullable=False)
    op.alter_column("itinerary_stops", "stop_order", nullable=False)
    op.alter_column("itinerary_stops", "departure_at", nullable=False)
    op.alter_column("itinerary_stops", "activity_duration_min", nullable=False)
    op.alter_column("itinerary_stops", "cost_vnd", type_=sa.BigInteger(), postgresql_using="cost_vnd::bigint")
    op.create_foreign_key("fk_itinerary_stops_poi_id_pois", "itinerary_stops", "pois", ["poi_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_itinerary_stop_order", "itinerary_stops", ["itinerary_id", "stop_order"])
    op.create_index("ix_itinerary_stops_poi_id", "itinerary_stops", ["poi_id"])

    # New tables from the team's ERD (plus feedbacks, referenced in its relation diagram).
    # Create only the tables this revision introduces. Using the whole live metadata here would also create every table
    # and column added by later revisions, which then fail with "already exists" on a clean database.
    new_tables = [Base.metadata.tables[name] for name in ("events", "itinerary_versions", "intent_similarities")]
    Base.metadata.create_all(bind=connection, tables=new_tables)
    # feedbacks as it was at this revision: the live model also has user_id (0004) and the labelling columns (0003).
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("itinerary_id", sa.String(36), sa.ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_feedback_rating_range"),
    )
    # Columns of those tables that later revisions add themselves.
    for table, column in LATER_COLUMNS:
        op.drop_column(table, column)

    # `reason_codes` was JSON in the first schema; preserve its values while adopting text[].
    _replace_json_array_column("decision_logs", "reason_codes")
    op.add_column("decision_logs", sa.Column("trigger_event_id", sa.String(36), nullable=True))
    op.add_column("decision_logs", sa.Column("base_version", sa.Integer(), nullable=True))
    op.add_column("decision_logs", sa.Column("new_version", sa.Integer(), nullable=True))
    op.add_column("decision_logs", sa.Column("preserved_intents", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")))
    op.add_column("decision_logs", sa.Column("lost_intents", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")))
    op.add_column("decision_logs", sa.Column("comparative_metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("decision_logs", sa.Column("explanation_vi", sa.Text(), nullable=True))
    op.alter_column("decision_logs", "rejected_candidates", type_=postgresql.JSONB(), postgresql_using="rejected_candidates::jsonb")
    op.create_foreign_key("fk_decision_logs_trigger_event_id_events", "decision_logs", "events", ["trigger_event_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_decision_logs_trigger_event_id", "decision_logs", ["trigger_event_id"])

    # Preserve a current snapshot for every itinerary that existed before version history.
    connection.execute(sa.text("""
        INSERT INTO itinerary_versions
            (id, itinerary_id, version_number, stops_snapshot, total_cost_vnd, total_travel_time_s, preserved_intents_ratio, created_at)
        SELECT
            md5(i.id || '\\:v' || i.current_version)::uuid::text, i.id, i.current_version,
            COALESCE((
                SELECT jsonb_agg(jsonb_build_object(
                    'stop_id', s.id, 'stop_order', s.stop_order, 'poi_id', s.poi_id,
                    'experience_id', s.experience_id, 'slot_id', s.slot_id,
                    'arrival_at', s.arrival_at, 'departure_at', s.departure_at,
                    'cost_vnd', s.cost_vnd, 'is_locked', s.is_locked
                ) ORDER BY s.stop_order)
                FROM itinerary_stops s WHERE s.itinerary_id = i.id
            ), '[]'::jsonb),
            i.estimated_cost_vnd, 0, NULL, i.created_at
        FROM itineraries i
        ON CONFLICT (itinerary_id, version_number) DO NOTHING
    """))

    # Existing point data was geography; the team's ERD explicitly uses geometry(Point,4326).
    _normalize_poi_geometry()


def downgrade() -> None:
    # Downgrade is available for ordinary-sized legacy data. Refuse values that cannot
    # fit the original int32 price columns instead of silently truncating them.
    connection = op.get_bind()
    for table, column in (("experiences", "price_vnd"), ("itineraries", "budget_vnd"), ("itineraries", "estimated_cost_vnd"), ("itinerary_stops", "cost_vnd")):
        too_large = connection.execute(sa.text(
            f"SELECT 1 FROM {table} WHERE {column} < -2147483648 OR {column} > 2147483647 LIMIT 1"
        )).first()
        if too_large:
            raise RuntimeError(f"Cannot downgrade {table}.{column}: value exceeds the original integer range")

    op.execute("ALTER TABLE pois ALTER COLUMN geom TYPE geography(Point, 4326) USING geom::geography")
    op.drop_constraint("ck_experience_slots_status", "experience_slots", type_="check")
    op.drop_index("ix_decision_logs_trigger_event_id", table_name="decision_logs")
    op.drop_constraint("fk_decision_logs_trigger_event_id_events", "decision_logs", type_="foreignkey")
    for column in (
        "trigger_event_id", "base_version", "new_version", "preserved_intents", "lost_intents",
        "comparative_metrics", "explanation_vi",
    ):
        op.drop_column("decision_logs", column)
    # Restore the two pre-existing JSON arrays before returning to revision 0001.
    for table, column in (("decision_logs", "reason_codes"), ("experiences", "intent_tags")):
        legacy = f"{column}_array_new"
        op.alter_column(table, column, new_column_name=legacy)
        op.add_column(table, sa.Column(column, sa.JSON(), nullable=True))
        connection.execute(sa.text(f"UPDATE {table} SET {column} = to_json({legacy})"))
        op.alter_column(table, column, nullable=False, server_default=sa.text("'[]'::json"))
        op.drop_column(table, legacy)
    op.alter_column("decision_logs", "rejected_candidates", type_=sa.JSON(), postgresql_using="rejected_candidates::json")
    for table in ("feedbacks", "events", "itinerary_versions", "intent_similarities"):
        op.drop_table(table)
    op.drop_index("ix_itinerary_stops_poi_id", table_name="itinerary_stops")
    op.drop_constraint("uq_itinerary_stop_order", "itinerary_stops", type_="unique")
    op.drop_constraint("fk_itinerary_stops_poi_id_pois", "itinerary_stops", type_="foreignkey")
    for column in ("poi_id", "stop_order", "departure_at", "wait_duration_min", "activity_duration_min", "status", "is_locked"):
        op.drop_column("itinerary_stops", column)
    op.drop_index("ix_itineraries_user_session_id", table_name="itineraries")
    for column in ("user_session_id", "city", "planned_date", "start_time", "return_deadline", "travel_mode", "target_intents", "current_version"):
        op.drop_column("itineraries", column)
    op.drop_index("ix_pois_district", table_name="pois")
    for column in ("district", "source_attribution", "is_in_pilot_polygon", "image_urls"):
        op.drop_column("pois", column)
    for column in ("title", "is_hands_on", "is_indoor"):
        op.drop_column("experiences", column)
    op.alter_column("experiences", "price_vnd", type_=sa.Integer(), postgresql_using="price_vnd::integer")
    op.alter_column("itineraries", "budget_vnd", type_=sa.Integer(), postgresql_using="budget_vnd::integer")
    op.alter_column("itineraries", "estimated_cost_vnd", type_=sa.Integer(), postgresql_using="estimated_cost_vnd::integer")
    op.alter_column("itinerary_stops", "cost_vnd", type_=sa.Integer(), postgresql_using="cost_vnd::integer")
    op.drop_constraint("uq_providers_slug", "providers", type_="unique")
    for column in ("slug", "address", "is_active", "verification_status", "portal_access_key"):
        op.drop_column("providers", column)
