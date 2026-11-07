"""P10-S04 model promotion and rollback (REQ-P10-S04-002, REQ-P10-S04-003).

Every command edits ``configs/models/registry.json``; commit the change so the
promotion is reviewed.  The service loads whatever ``active-config`` prints:

    DFU_INFERENCE_CONFIG=$(python scripts/deployment/promote_model.py active-config)

Commands::

    python scripts/deployment/promote_model.py list
    python scripts/deployment/promote_model.py gates <model_version>
    python scripts/deployment/promote_model.py promote <model_version> --approved-by "<name>" [--canary] [--dry-run]
    python scripts/deployment/promote_model.py rollback --approved-by "<name>"
    python scripts/deployment/promote_model.py stop-canary <model_version> --reason "<why>"
    python scripts/deployment/promote_model.py active-config

Analyses keep the ``model_version`` they were made with, so neither a promotion
nor a rollback changes an existing result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mlops.gates import run_gates  # noqa: E402
from src.mlops.registry import DEFAULT_REGISTRY, Registry, RegistryError  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="where artifact and report paths start")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    commands.add_parser("active-config")
    gates = commands.add_parser("gates")
    gates.add_argument("model_version")
    promote = commands.add_parser("promote")
    promote.add_argument("model_version")
    promote.add_argument("--approved-by", required=True)
    promote.add_argument("--canary", action="store_true", help="Promote to CANARY instead of ACTIVE")
    promote.add_argument("--dry-run", action="store_true")
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--approved-by", required=True)
    rollback.add_argument("--dry-run", action="store_true")
    stop = commands.add_parser("stop-canary")
    stop.add_argument("model_version")
    stop.add_argument("--reason", required=True)
    args = parser.parse_args(argv)

    try:
        registry = Registry(args.registry, args.root)
        if args.command == "list":
            for record in registry.data["models"]:
                print(f"{record['status']:<9} {record['model_version']}  {record['runtime']}  "
                      f"approved_by={record['approved_by']}")
            return 0
        if args.command == "active-config":
            active = registry.active()
            if active is None:
                raise RegistryError("No ACTIVE model")
            registry.verify_artifact(active)
            print(active["inference_config"])
            return 0
        if args.command == "gates":
            report = run_gates(registry.get(args.model_version), registry.active(), registry.root)
            print(json.dumps(report, indent=2))
            return 0 if all(gate["passed"] for gate in report.values()) else 1
        if args.command == "promote":
            candidate = registry.get(args.model_version)
            registry.verify_artifact(candidate)
            report = run_gates(candidate, registry.active(), registry.root)
            print(json.dumps(report, indent=2))
            registry.promote(args.model_version, args.approved_by, report, to="CANARY" if args.canary else "ACTIVE")
        elif args.command == "rollback":
            restored = registry.rollback(args.approved_by)
            registry.verify_artifact(registry.get(restored))
            print(f"ACTIVE is now {restored}; restart the service with its inference config")
        elif args.command == "stop-canary":
            registry.stop_canary(args.model_version, args.reason)
        if getattr(args, "dry_run", False):
            print("Dry run: registry not written")
        else:
            registry.save()
            print(f"Wrote {args.registry}")
        return 0
    except RegistryError as error:
        print(f"Refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
