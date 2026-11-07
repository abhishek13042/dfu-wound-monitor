"""P09-S03: corrected masks, kept beside the analysis they correct.

Each correction is a new numbered version for its analysis; the analysis row
and its artifacts are never changed (REQ-P09-S03-002).  ``research_opt_in``
starts at 0, so nothing is used for research without a choice
(REQ-P09-S03-005).

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mask_corrections",
        sa.Column("correction_id", sa.Text(), nullable=False),
        sa.Column("analysis_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("measurement_json", sa.Text(), nullable=False),
        sa.Column("research_opt_in", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("correction_id", name="pk_mask_corrections"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.analysis_id"], name="fk_mask_corrections_analysis_id",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.user_id"], name="fk_mask_corrections_owner_id",
                                ondelete="CASCADE"),
        sa.UniqueConstraint("analysis_id", "version", name="uq_mask_corrections_analysis_version"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_mask_corrections_sha256_length"),
        sa.CheckConstraint("version >= 1", name="ck_mask_corrections_version_positive"),
        sa.CheckConstraint("research_opt_in IN (0, 1)", name="ck_mask_corrections_research_opt_in"),
    )
    op.create_index("idx_mask_corrections_owner", "mask_corrections", ["owner_id"])


def downgrade() -> None:
    op.drop_index("idx_mask_corrections_owner", "mask_corrections")
    op.drop_table("mask_corrections")
