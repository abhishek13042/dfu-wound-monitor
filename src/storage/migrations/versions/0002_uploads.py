"""P07-S03: the uploads table.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("upload_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("declared_size", sa.Integer(), nullable=False),
        sa.Column("declared_sha256", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text()),
        sa.Column("format", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.CheckConstraint("status IN ('PENDING', 'VERIFIED', 'REJECTED')", name="ck_uploads_status"),
        sa.CheckConstraint("length(declared_sha256) = 64", name="ck_uploads_declared_sha256_length"),
        sa.PrimaryKeyConstraint("upload_id", name="pk_uploads"),
    )
    op.create_index("idx_uploads_expires", "uploads", ["expires_at"])


def downgrade() -> None:
    op.drop_table("uploads")
