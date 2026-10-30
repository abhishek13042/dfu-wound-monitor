"""P07-S02 database plumbing: URLs, engines, schema migration, storage errors.

``DFU_DATABASE_URL`` selects the database.  A plain path means SQLite, which is
kept for tests and local use; PostgreSQL is the production target and the
authority when the two disagree.

SQLite is migrated when opened, because a local run has no deploy step.
PostgreSQL is shared by several instances, so its schema changes only through
an explicit ``migrate`` call; until then ``/health/ready`` reports the database
as not ready.

Retention (prototype): data are kept until ``delete_case`` is called.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Connection, Engine, make_url

SCHEMA_VERSION = 4
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MIGRATION_LOCK_KEY = 120_712  # any constant shared by every instance
LEGACY_VERSION = "0001"       # the only schema the hand-written migrator ever produced


class StorageError(Exception):
    category = "PERSISTENCE"

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "code": self.code, "message": self.message}


class NotFoundError(StorageError):
    pass


def database_url(target: str | Path) -> str:
    """Normalise a path or URL to a SQLAlchemy URL that names its driver."""

    value = str(target)
    if "://" not in value:
        return f"sqlite:///{Path(value).resolve().as_posix()}"
    if value.startswith("postgres://"):
        value = "postgresql://" + value.removeprefix("postgres://")
    if value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value.removeprefix("postgresql://")
    return value


def is_sqlite(url: str) -> bool:
    return make_url(database_url(url)).get_backend_name() == "sqlite"


def create_database_engine(url: str, *, foreign_keys: bool = True) -> Engine:
    url = database_url(url)
    if not is_sqlite(url):
        # Small pool, because serverless PostgreSQL limits connections.  pre_ping
        # replaces connections the provider closed while idle.
        return create_engine(url, pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=300,
                             connect_args={"connect_timeout": 10})

    engine = create_engine(url, connect_args={"timeout": 30, "check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _configure(connection: Any, _: Any) -> None:
        # The driver's implicit BEGIN is turned off so that the listener below
        # controls it.  This pragma has no effect once a transaction is open.
        connection.isolation_level = None
        connection.execute(f"PRAGMA foreign_keys = {'ON' if foreign_keys else 'OFF'}")

    @event.listens_for(engine, "begin")
    def _begin(connection: Connection) -> None:
        # IMMEDIATE takes the write lock up front.  A deferred transaction that
        # reads and then writes fails at once if another writer got in between.
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def migration_config(connection: Connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR).replace("%", "%%"))
    config.attributes["connection"] = connection
    return config


def installed_version(connection: Connection) -> int:
    """The schema revision the database is at; 0 when it has never been migrated."""

    tables = inspect(connection).get_table_names()
    if "alembic_version" in tables:
        return int(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none() or 0)
    if "schema_version" in tables:
        return int(LEGACY_VERSION)
    return 0


def migrate(url: str) -> list[int]:
    """Bring the schema to head and return the revisions applied."""

    # Foreign keys stay off on SQLite because Alembic rebuilds a table to alter
    # it there, and dropping the old table with them on would cascade-delete the
    # child rows.  PRAGMA foreign_key_check below replaces that protection.
    engine = create_database_engine(url, foreign_keys=False)
    try:
        with engine.begin() as connection:
            if not is_sqlite(url):
                connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
            before = installed_version(connection)
            config = migration_config(connection)
            tables = inspect(connection).get_table_names()
            if "schema_version" in tables and "alembic_version" not in tables:
                command.stamp(config, LEGACY_VERSION)
                connection.execute(text("DROP TABLE schema_version"))
            command.upgrade(config, "head")
            if is_sqlite(url):
                violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise StorageError("MIGRATION_FAILED", f"Foreign key violations after migration: {violations[:5]}")
            return list(range(before + 1, installed_version(connection) + 1))
    finally:
        engine.dispose()
