"""Export the corrected masks their owners chose to share for research (P09-S03).

Only corrections with ``research_opt_in`` set are written.  The export is a
review queue, not a training set: every row is marked ``review_status:
UNREVIEWED`` and nothing here feeds training (REQ-P09-S03-005).  Masks are
written by their hash, with no user, case or image identifier beyond the
analysis and correction IDs.

    python scripts/data/export_corrections.py --output data/corrections_review
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.api.service import ApiSettings  # noqa: E402
from src.storage.blobs import create_blob_store  # noqa: E402
from src.storage.repository import Repository  # noqa: E402


def export(db: Repository, blobs, output: Path) -> dict:
    masks = output / "masks"
    masks.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in db.research_corrections():
        data = blobs.get(row["storage_key"])
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise SystemExit(f"Correction {row['correction_id']} failed its hash check")
        (masks / f"{row['sha256']}.png").write_bytes(data)
        rows.append({"correction_id": row["correction_id"], "analysis_id": row["analysis_id"],
                     "version": row["version"], "created_at": row["created_at"], "sha256": row["sha256"],
                     "mask": f"masks/{row['sha256']}.png", "review_status": "UNREVIEWED"})
    manifest = {"source": "P09-S03 research opt-in", "count": len(rows),
                "note": "Unreviewed corrections. Not training labels until each is reviewed.",
                "corrections": rows}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = ApiSettings(load_model=False)
    db = Repository(settings.database_url or settings.data_dir / "dfu_wound_monitor.sqlite3")
    blobs = create_blob_store(settings.storage_backend, settings.data_dir, settings.s3_bucket, settings.s3_endpoint)
    manifest = export(db, blobs, args.output)
    print(f"Wrote {manifest['count']} corrections to {args.output}")


if __name__ == "__main__":
    main()
