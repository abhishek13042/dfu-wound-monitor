# P06-S03 — Deployment and Portfolio Release

## Status

`COMPLETED` — `docs/release/RELEASE.md`, `scripts/deployment/smoke_test.py`, `scripts/deployment/build_release_manifest.py` (producing `reports/final/release_manifest.json`) and `tests/release/test_p06_release.py`. A clean start from an empty data directory is verified by the smoke test. A fresh-virtualenv install was not exercised on a second machine.

## Objective

Package and document a reproducible technical release of the approved MVP.

## Scope

Runtime packaging, configuration, migrations, startup, health checks, demo
data, artifact/version policy, limitations, and final portfolio documentation.

## Non-Goals

Regulatory approval, clinical deployment, production patient data, or
unapproved security/compliance claims.

## Requirements

- **REQ-P06-S03-001:** A clean environment SHALL be able to install and start
  the documented system.
- **REQ-P06-S03-002:** Health checks SHALL distinguish service readiness from
  model readiness.
- **REQ-P06-S03-003:** Release artifacts SHALL include versions, configs,
  limitations, and reproducible commands.
- **REQ-P06-S03-004:** Demo data and documentation SHALL not imply clinical
  validation or treatment capability.

## Tests and Acceptance

Clean-install, migration, startup, health, smoke-inference, artifact, and
documentation review checks SHALL pass. The final release checklist and
traceability sign-off are required.
