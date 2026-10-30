"""P07-S02 and P07-S04: migrations reach the same schema as the models, and back."""

from __future__ import annotations

import sqlite3

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.storage.database import (
    LEGACY_VERSION,
    SCHEMA_VERSION,
    create_database_engine,
    installed_version,
    migrate,
    migration_config,
)
from src.storage.models import DEMO_OWNER, Base
from src.storage.repository import Repository


def test_head_matches_schema_version(database_url):
    migrate(database_url)
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        assert installed_version(connection) == SCHEMA_VERSION
    engine.dispose()


def test_migrations_match_the_models(database_url):
    migrate(database_url)
    engine = create_database_engine(database_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []
    engine.dispose()


def test_migration_round_trip(database_url):
    migrate(database_url)
    engine = create_database_engine(database_url, foreign_keys=False)
    with engine.begin() as connection:
        command.downgrade(migration_config(connection), "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
    with engine.begin() as connection:
        command.upgrade(migration_config(connection), "head")
        assert installed_version(connection) == SCHEMA_VERSION
    engine.dispose()


def test_legacy_sqlite_database_is_adopted_without_data_loss(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    engine = create_database_engine(str(path), foreign_keys=False)
    with engine.begin() as connection:
        command.upgrade(migration_config(connection), LEGACY_VERSION)
    engine.dispose()
    raw = sqlite3.connect(path)
    raw.executescript("""
        DROP TABLE alembic_version;
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (1, '2026-01-01');
        INSERT INTO cases VALUES ('c1', 'UNKNOWN', 'SYNTHETIC', NULL, NULL, '2026-01-01', '{}');
    """)
    raw.close()
    repository = Repository(path)
    assert repository.schema_version() == SCHEMA_VERSION
    assert "schema_version" not in inspect(repository.engine).get_table_names()
    repository.close()
    raw = sqlite3.connect(path)
    assert raw.execute("SELECT count(*) FROM cases").fetchone() == (1,)
    raw.close()


def test_owner_migration(database_url):
    migrate(database_url)
    engine = create_database_engine(database_url, foreign_keys=False)
    with engine.begin() as connection:
        command.downgrade(migration_config(connection), "0002")
        connection.execute(text("INSERT INTO cases (case_id, identity_status, data_source, created_at, record_json) "
                                "VALUES ('c1', 'UNKNOWN', 'SYNTHETIC', '2026-01-01', '{}')"))
        connection.execute(text("INSERT INTO examinations (examination_id, case_id, timestamp_source, created_at, "
                                "record_json) VALUES ('e1', 'c1', 'UNKNOWN', '2026-01-01', '{}')"))
    with engine.begin() as connection:
        command.upgrade(migration_config(connection), "head")
        owners = {connection.scalar(text(f"SELECT owner_id FROM {table}")) for table in ("cases", "examinations")}
    engine.dispose()
    assert owners == {DEMO_OWNER}

    # The SQLite upgrade rebuilds each table, which must not lose a constraint.
    engine = create_database_engine(database_url)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE cases SET identity_status = 'BOGUS'"))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE cases SET owner_id = 'nobody'"))
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM cases"))
        assert connection.scalar(text("SELECT count(*) FROM examinations")) == 0
    engine.dispose()


def test_downgrade_refuses_to_merge_accounts(database_url):
    repository = Repository(database_url)
    migrate(database_url)
    repository.ensure_user("https://signin.test|someone")
    repository.close()
    engine = create_database_engine(database_url, foreign_keys=False)
    with pytest.raises(RuntimeError, match="private accounts"), engine.begin() as connection:
        command.downgrade(migration_config(connection), "0002")
    engine.dispose()


def test_postgresql_is_never_migrated_implicitly(database_url, monkeypatch):
    calls = []
    monkeypatch.setattr("src.storage.repository.migrate", lambda url: calls.append(url) or [])
    Repository(database_url).close()
    assert bool(calls) == database_url.endswith(".sqlite3")
