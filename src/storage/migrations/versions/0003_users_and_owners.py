"""P07-S04: users, and an owner on every row a user can reach.

Existing rows go to the ``demo`` user, which has no subject, so no token can
reach them (REQ-P07-S04-005).

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

OWNED_TABLES = ("cases", "examinations", "images", "analyses", "uploads")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_users"),
        sa.UniqueConstraint("subject", name="uq_users_subject"),
    )
    op.execute("INSERT INTO users (user_id, subject, created_at) VALUES ('demo', NULL, '1970-01-01T00:00:00+00:00')")
    for table in OWNED_TABLES:
        op.add_column(table, sa.Column("owner_id", sa.Text()))
        op.execute(f"UPDATE {table} SET owner_id = 'demo'")
        with op.batch_alter_table(table) as batch:
            batch.alter_column("owner_id", existing_type=sa.Text(), nullable=False)
            batch.create_foreign_key(f"fk_{table}_owner_id", "users", ["owner_id"], ["user_id"], ondelete="CASCADE")
            batch.create_index(f"idx_{table}_owner", ["owner_id"])


def downgrade() -> None:
    users = op.get_bind().scalar(sa.text("SELECT count(*) FROM users WHERE user_id <> 'demo'"))
    if users:
        raise RuntimeError(f"Refusing to merge {users} private accounts into one shared workspace")
    for table in OWNED_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"idx_{table}_owner")
            batch.drop_constraint(f"fk_{table}_owner_id", type_="foreignkey")
            batch.drop_column("owner_id")
    op.drop_table("users")
