"""Write the /api/v2 OpenAPI document that web/lib/api/schema.d.ts is generated from.

Run from the repository root: python web/scripts/export_openapi.py web/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.api.app import create_app  # noqa: E402
from src.api.service import ApiSettings  # noqa: E402

schema = create_app(ApiSettings(load_model=False)).openapi()
schema["paths"] = {path: item for path, item in schema["paths"].items() if not path.startswith("/api/v1")}
# Bytes, so the file is LF on every platform and Windows output matches what CI generates.
Path(sys.argv[1]).write_bytes((json.dumps(schema, indent=2, sort_keys=True) + "\n").encode("utf-8"))
