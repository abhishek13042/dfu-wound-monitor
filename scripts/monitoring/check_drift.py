"""P10-S04: compare recent analyses with the drift reference and write a report.

Reads only the analyses table (summary numbers in ``record_json``); no image
is opened.  Run it on a schedule; exit code 1 means input drift, and the
report says it is a change in inputs, not in accuracy.

    python scripts/monitoring/check_drift.py --database-url "$DFU_DATABASE_URL" --days 7 \
        --output reports/monitoring/drift_$(date +%F).json

Exit codes: 0 stable or not enough data, 1 drift, 2 refused (no reference, bad arguments).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from src.mlops.drift import check, features_from_record  # noqa: E402
from src.storage.database import create_database_engine  # noqa: E402
from src.storage.models import Analysis  # noqa: E402

DEFAULT_REFERENCE = PROJECT_ROOT / "configs/models/drift_reference_fuseg2021.json"


def recent_rows(url: str, days: float, model_version: str | None) -> list[dict]:
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    query = select(Analysis.record_json).where(Analysis.created_at >= cutoff)
    if model_version:
        query = query.where(Analysis.model_version == model_version)
    engine = create_database_engine(url)
    try:
        with engine.connect() as connection:
            return [features_from_record(json.loads(text)) for (text,) in connection.execute(query)]
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database-url", default=os.environ.get("DFU_DATABASE_URL"))
    parser.add_argument("--days", type=float, default=7)
    parser.add_argument("--model-version", help="only analyses made by this model")
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.database_url or not args.reference.exists():
        print("Refused: needs --database-url (or DFU_DATABASE_URL) and an existing --reference", file=sys.stderr)
        return 2

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    report = check(reference, recent_rows(args.database_url, args.days, args.model_version))
    report["window_days"], report["model_version"] = args.days, args.model_version
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if report["status"] == "DRIFT" else 0


if __name__ == "__main__":
    sys.exit(main())
