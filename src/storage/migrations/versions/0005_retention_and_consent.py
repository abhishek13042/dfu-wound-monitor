"""P10-S03: a keep flag on cases, and the consent record.

Images and results in a case nobody chose to keep are deleted after
``DFU_RETENTION_HOURS`` (REQ-P10-S03-001).  Existing cases start as not kept,
because keeping data needs an explicit choice.  A consent row names the text
version a user accepted and when (REQ-P10-S03-003).

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("keep", sa.Integer(), nullable=False, server_default="0"))
        batch.create_check_constraint(op.f("ck_cases_keep"), "keep IN (0, 1)")
    op.create_index("idx_analyses_created", "analyses", ["created_at"])
    op.create_index("idx_images_created", "images", ["created_at"])
    op.create_index("idx_uploads_created", "uploads", ["created_at"])
    op.create_table(
        "consents",
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("text_version", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "text_version", name="pk_consents"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.user_id"], name="fk_consents_owner_id", ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("consents")
    op.drop_index("idx_uploads_created", "uploads")
    op.drop_index("idx_images_created", "images")
    op.drop_index("idx_analyses_created", "analyses")
    with op.batch_alter_table("cases") as batch:
        batch.drop_constraint(op.f("ck_cases_keep"), type_="check")
        batch.drop_column("keep")
