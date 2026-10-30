"""P07-S05: the state of each background analysis.

Jobs are a separate table because ``analyses`` keeps its meaning: a row there is
a finished result.  The two share ``analysis_id``, so a repeat cannot store a
second result.  The foreign keys cascade, so deleting a user or a case stops
their waiting jobs.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("analysis_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("upload_id", sa.Text(), nullable=False),
        sa.Column("examination_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("requeued", sa.Integer(), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("error_json", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("analysis_id", name="pk_analysis_jobs"),
        sa.UniqueConstraint("upload_id", name="uq_analysis_jobs_upload_id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.user_id"], name="fk_analysis_jobs_owner_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["examination_id"], ["examinations.examination_id"],
                                name="fk_analysis_jobs_examination_id", ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'QUALITY_REJECTED', 'FAILED')",
                           name="ck_analysis_jobs_job_status"),
    )
    op.create_index("idx_analysis_jobs_status", "analysis_jobs", ["status", "updated_at"])
    op.create_index("idx_analysis_jobs_owner", "analysis_jobs", ["owner_id"])


def downgrade() -> None:
    op.drop_table("analysis_jobs")
