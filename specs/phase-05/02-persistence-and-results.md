# P05-S02 — Persistence and Model-Result Storage

## Status

`COMPLETED` — `src/storage/database.py`: SQLite with versioned migrations, foreign keys, transactional saves, a content-addressed blob store, and case deletion that cascades to the blobs. Results survive a restart. Tests: `tests/api/test_p05_storage.py`, and the restart test in `tests/api/test_p05_api.py`.

## Objective

Persist examination references and technical inference results without losing
provenance or confusing identity levels.

## Scope

Schema/migrations, image references, cases, examinations, quality results,
model versions, masks/artifact references, measurements, failures, and
retention/deletion behavior for the prototype.

## Non-Goals

Production clinical records, multi-tenant security, or unapproved cloud
storage.

## Requirements

- **REQ-P05-S02-001:** Records SHALL distinguish case, examination, image,
  inference, and model-version identifiers.
- **REQ-P05-S02-002:** Stored results SHALL be traceable to input and config
  artifacts.
- **REQ-P05-S02-003:** Invalid writes SHALL be rejected transactionally.
- **REQ-P05-S02-004:** Migrations and local setup SHALL be reproducible.

## Tests and Acceptance

Migration, CRUD, provenance, invalid-write, rollback, and round-trip tests
SHALL pass.
