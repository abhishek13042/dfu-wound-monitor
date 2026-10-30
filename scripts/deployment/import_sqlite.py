"""Copy a P05 SQLite database into an empty PostgreSQL database.

Nothing is committed unless every record passes its schema and the row counts
and checksums read back from the target equal those of the source.  The source
is opened read-only and is never changed.

    python scripts/deployment/import_sqlite.py --source runtime/dfu_wound_monitor.sqlite3 --target postgresql://...

Exit codes: 0 imported, 1 refused or failed (the target's rows are unchanged).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import Table, func, select, true  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402

from src.longitudinal.records import (  # noqa: E402
    AnalysisRecord,
    CaseRecord,
    ExaminationRecord,
    ImageRecord,
    RecordValidationError,
)
from src.storage.database import StorageError, create_database_engine, migrate  # noqa: E402
from src.storage.models import DEMO_OWNER, Base  # noqa: E402

VALIDATORS: dict[str, tuple[str, Callable[[str], Any]]] = {
    "model_versions": ("details_json", json.loads),
    "cases": ("record_json", CaseRecord.model_validate_json),
    "examinations": ("record_json", ExaminationRecord.model_validate_json),
    "images": ("record_json", ImageRecord.model_validate_json),
    "analyses": ("record_json", AnalysisRecord.model_validate_json),
}


# Staged uploads expire, and a job in progress needs its upload.
TABLES = [table for table in Base.metadata.sorted_tables if table.name not in ("uploads", "analysis_jobs")]


class ImportRefused(Exception):
    pass


def _imported_rows(table: Table) -> Any:
    """Every migrated database already holds the demo user, so it is not part of the copy."""

    return table.c.user_id != DEMO_OWNER if table.name == "users" else true()


def _checksum(rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = sorted(json.dumps([row[column] for column in columns]) for row in rows)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _read_source(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.is_file():
        raise ImportRefused(f"Source does not exist: {path}")
    source = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        present = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        rows = {table.name: [dict(row) for row in source.execute(f"SELECT * FROM {table.name}")]
                if table.name in present else [] for table in TABLES}
    except sqlite3.Error as error:
        raise ImportRefused(f"Source is not a readable DFU database: {error}") from error
    finally:
        source.close()
    rows["users"] = [row for row in rows["users"] if row["user_id"] != DEMO_OWNER]
    for table in TABLES:
        if "owner_id" in table.c:  # data from before accounts belongs to the demo user
            for row in rows[table.name]:
                row.setdefault("owner_id", DEMO_OWNER)
    for table, (column, validate) in VALIDATORS.items():
        for number, row in enumerate(rows[table], start=1):
            try:
                validate(row[column])
            except (ValueError, RecordValidationError) as error:
                raise ImportRefused(f"{table} row {number} failed validation: {error}") from error
    return rows


def _copy(connection: Connection, rows: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    for table in TABLES:
        if connection.scalar(select(func.count()).select_from(table).where(_imported_rows(table))):
            raise ImportRefused(f"Target table is not empty: {table.name}")
    report: dict[str, dict[str, Any]] = {}
    for table in TABLES:
        table_rows = rows[table.name]
        columns = [column.name for column in table.columns if not table_rows or column.name in table_rows[0]]
        if table_rows:
            connection.execute(table.insert(), [{column: row[column] for column in columns} for row in table_rows])
        selected = [table.c[column] for column in columns]
        copied = [dict(row._mapping) for row in connection.execute(select(*selected).where(_imported_rows(table)))]
        expected = _checksum(table_rows, columns)
        if len(copied) != len(table_rows) or _checksum(copied, columns) != expected:
            raise ImportRefused(f"Verification failed for {table.name}")
        report[table.name] = {"rows": len(copied), "sha256": expected}
    return report


def import_database(source: Path, target: str) -> dict[str, dict[str, Any]]:
    rows = _read_source(source)
    migrate(target)
    engine = create_database_engine(target)
    try:
        with engine.begin() as connection:
            return _copy(connection, rows)
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", required=True, help="Database URL")
    args = parser.parse_args()
    try:
        report = import_database(args.source, args.target)
    except (ImportRefused, StorageError) as error:
        print(f"Import refused, target unchanged: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "IMPORTED", "tables": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
