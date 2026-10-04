"""Add quarantined POI source imports.

Revision ID: 0010_place_import_staging
Revises: 0009_integration_secrets
"""

import sqlalchemy as sa
from alembic import op


revision = "0010_place_import_staging"
down_revision = "0009_integration_secrets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "place_import_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("worksheet_name", sa.String(100), nullable=False),
        sa.Column("imported_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_sha256", name="uq_place_import_batch_sha256"),
    )
    op.create_index("ix_place_import_batches_imported_by", "place_import_batches", ["imported_by"])

    op.create_table(
        "place_import_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("place_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("quality_flags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="needs_enrichment"),
        sa.Column("target_poi_id", sa.String(36), sa.ForeignKey("pois.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "external_id", name="uq_place_candidate_batch_external_id"),
    )
    op.create_index("ix_place_import_candidates_batch_id", "place_import_candidates", ["batch_id"])
    op.create_index("ix_place_import_candidates_name", "place_import_candidates", ["name"])
    op.create_index("ix_place_import_candidates_kind", "place_import_candidates", ["kind"])
    op.create_index("ix_place_import_candidates_review_status", "place_import_candidates", ["review_status"])
    op.create_index("ix_place_import_candidates_target_poi_id", "place_import_candidates", ["target_poi_id"])


def downgrade() -> None:
    op.drop_table("place_import_candidates")
    op.drop_index("ix_place_import_batches_imported_by", table_name="place_import_batches")
    op.drop_table("place_import_batches")
