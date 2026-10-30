"""Initial schema: the six P05-S02 tables.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_versions",
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("architecture", sa.Text(), nullable=False),
        sa.Column("checkpoint_sha256", sa.Text(), nullable=False),
        sa.Column("inference_config_sha256", sa.Text(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("registered_at", sa.Text(), nullable=False),
        sa.CheckConstraint("length(checkpoint_sha256) = 64", name="ck_model_versions_checkpoint_sha256_length"),
        sa.CheckConstraint("length(inference_config_sha256) = 64",
                           name="ck_model_versions_inference_config_sha256_length"),
        sa.PrimaryKeyConstraint("model_version", name="pk_model_versions"),
    )
    op.create_table(
        "cases",
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("identity_status", sa.Text(), nullable=False),
        sa.Column("data_source", sa.Text(), nullable=False),
        sa.Column("external_reference", sa.Text()),
        sa.Column("label", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("record_json", sa.Text(), nullable=False),
        sa.CheckConstraint("identity_status IN ('VERIFIED', 'UNVERIFIED', 'UNKNOWN')",
                           name="ck_cases_identity_status"),
        sa.PrimaryKeyConstraint("case_id", name="pk_cases"),
    )
    op.create_table(
        "examinations",
        sa.Column("examination_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text()),
        sa.Column("captured_at", sa.Text()),
        sa.Column("timestamp_source", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("record_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_examinations_case_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("examination_id", name="pk_examinations"),
    )
    op.create_index("idx_examinations_case", "examinations", ["case_id", "captured_at"])
    op.create_table(
        "images",
        sa.Column("image_id", sa.Text(), nullable=False),
        sa.Column("examination_id", sa.Text()),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("record_json", sa.Text(), nullable=False),
        sa.CheckConstraint("length(sha256) = 64", name="ck_images_sha256_length"),
        sa.ForeignKeyConstraint(["examination_id"], ["examinations.examination_id"],
                                name="fk_images_examination_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("image_id", name="pk_images"),
    )
    op.create_index("idx_images_examination", "images", ["examination_id"])
    op.create_table(
        "analyses",
        sa.Column("analysis_id", sa.Text(), nullable=False),
        sa.Column("image_id", sa.Text(), nullable=False),
        sa.Column("examination_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("record_json", sa.Text(), nullable=False),
        sa.CheckConstraint("status IN ('COMPLETED', 'QUALITY_REJECTED', 'FAILED')", name="ck_analyses_status"),
        sa.CheckConstraint("status != 'COMPLETED' OR model_version IS NOT NULL",
                           name="ck_analyses_completed_has_model"),
        sa.ForeignKeyConstraint(["image_id"], ["images.image_id"], name="fk_analyses_image_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["examination_id"], ["examinations.examination_id"],
                                name="fk_analyses_examination_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_version"], ["model_versions.model_version"],
                                name="fk_analyses_model_version"),
        sa.PrimaryKeyConstraint("analysis_id", name="pk_analyses"),
    )
    op.create_index("idx_analyses_examination", "analyses", ["examination_id", "created_at"])
    op.create_table(
        "artifacts",
        sa.Column("analysis_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.CheckConstraint("kind IN ('MASK', 'PROBABILITY')", name="ck_artifacts_kind"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_artifacts_sha256_length"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.analysis_id"], name="fk_artifacts_analysis_id",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("analysis_id", "kind", name="pk_artifacts"),
    )


def downgrade() -> None:
    for table in ("artifacts", "analyses", "images", "examinations", "cases", "model_versions"):
        op.drop_table(table)
