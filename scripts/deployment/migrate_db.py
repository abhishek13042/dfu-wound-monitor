"""Bring the database named by ``DFU_DATABASE_URL`` to the latest schema.

Safe to run from several instances at once: PostgreSQL migrations hold an
advisory lock.  Exit codes: 0 up to date, 1 failed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from src.storage.database import StorageError, migrate  # noqa: E402


def main() -> int:
    url = os.environ.get("DFU_DATABASE_URL")
    if not url:
        print("DFU_DATABASE_URL is not set", file=sys.stderr)
        return 1
    try:
        applied = migrate(url)
    except (SQLAlchemyError, StorageError) as error:
        # The URL holds the password, so only the error type is printed.
        print(f"Migration failed: {type(error).__name__}", file=sys.stderr)
        return 1
    print(f"Applied revisions: {applied or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
