"""Alembic environment.

``src.storage.database.migrate`` passes in an open connection.  The ``alembic``
command line has none, so it connects to ``DFU_DATABASE_URL``.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy.engine import Connection

from src.storage.database import create_database_engine
from src.storage.models import Base


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported; run against a database")

connection = context.config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    url = os.environ.get("DFU_DATABASE_URL")
    if not url:
        raise RuntimeError("Set DFU_DATABASE_URL to run alembic from the command line")
    engine = create_database_engine(url, foreign_keys=False)
    with engine.begin() as cli_connection:
        _run(cli_connection)
    engine.dispose()
