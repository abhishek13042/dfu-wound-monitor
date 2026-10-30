# P07-S02 — PostgreSQL and Managed Migrations

**Status:** `IN_PROGRESS`. Code complete and verified on a local PostgreSQL 16 server. The CI job has not run yet because nothing has been pushed.

## 1. Objective

Replace direct SQLite access with a database layer that several API and worker instances can share.

## 2. Scope

- SQLAlchemy 2 models for the seven existing tables
- Alembic migrations
- Repository layer that replaces `src/storage/database.py` calls
- One-way import from an existing SQLite database
- SQLite retained for tests and local use

## 3. Non-Goals

- Ownership columns, which belong to P07-S04
- Moving blobs, which belongs to P07-S03
- Read replicas or sharding

## 4. Requirements

- `REQ-P07-S02-001`: All database access SHALL go through a repository layer; route handlers SHALL NOT contain SQL.
- `REQ-P07-S02-002`: Alembic SHALL create the full schema from empty and SHALL upgrade and downgrade each revision.
- `REQ-P07-S02-003`: The test suite SHALL pass on both SQLite and PostgreSQL.
- `REQ-P07-S02-004`: An import tool SHALL copy a SQLite database to PostgreSQL and verify row counts and analysis checksums.
- `REQ-P07-S02-005`: The API `/api/v1` responses SHALL be unchanged, and `/health/ready` SHALL report database state.

## 5. Assumptions

- A managed PostgreSQL 16 service (Neon or Supabase) is available.
- Existing data is demo data, so a planned outage is acceptable during import.

## 6. Dependencies

- `P05-S02`
- `P07-S01`

## 7. Inputs

- Schema in `src/storage/database.py`
- `DFU_DATABASE_URL`

## 8. Outputs

- `src/storage/models.py`
- `src/storage/repository.py`
- `src/storage/migrations/`
- `scripts/deployment/import_sqlite.py`

## 9. Data / Interface Contract

`DFU_DATABASE_URL` selects the database and defaults to SQLite under `DFU_DATA_DIR`. Tables keep their names and meaning: `model_versions`, `cases`, `examinations`, `images`, `analyses`, `artifacts`. Alembic replaces `schema_version`.

## 10. Invariants

- Case, examination and analysis identity stay separate.
- A stored analysis keeps its model, config and calibration provenance.
- A migration never drops data without a reviewed revision.

## 11. Technical Design

Use the SQLAlchemy 2 typed ORM, with synchronous sessions, because handlers are synchronous. Each repository method is one transaction, which keeps today's guarantee that a failed write leaves nothing behind. Connection pooling is sized for serverless PostgreSQL limits. Tests create a fresh schema per test, using a PostgreSQL service container in CI.

SQLite is migrated when opened. PostgreSQL is only migrated by `scripts/deployment/migrate_db.py`, under an advisory lock, and `/health/ready` reports the database as not ready until the schema matches. SQLite migrations run with foreign keys off, because Alembic rebuilds a table to alter it and dropping the old one would otherwise cascade-delete its children; `PRAGMA foreign_key_check` then confirms the result.

## 12. Implementation Tasks

1. Write the models to match the current schema.
2. Generate and review the first Alembic revision.
3. Move each query behind the repository.
4. Add the PostgreSQL CI job.
5. Write and test the import tool.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Database unreachable at startup | `/health/ready` is 503 and `/health/live` stays 200 |
| Connection lost mid-request | `INFRASTRUCTURE_FAILURE`, with no partial analysis row |
| Unique constraint violated | `CONFLICT` 409 |
| Import counts differ | Import aborts and rolls back |

## 14. Tests

- Repository unit tests
- Migration upgrade and downgrade
- All API tests on both databases
- Import with a corrupted row

## 15. Acceptance Criteria

- All tests pass on both databases.
- The smoke test passes against PostgreSQL.
- No SQL remains in `src/api/`.

## 16. Evidence

- CI run with the PostgreSQL job
- Import report
- Migration review notes

## 17. Reproducibility

```bash
python -m alembic upgrade head
python -m pytest tests/storage tests/api -q
```

## 18. Risks / Limitations

- SQLite and PostgreSQL differ in type handling, so PostgreSQL is the authority when they disagree.
- Serverless databases have cold starts, so the readiness timeout must allow for them.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P07-S02-001` | `src/storage/repository.py` | `tests/storage/test_repository.py` | `test_api_layer_contains_no_sql`, 279 passed on PostgreSQL | COMPLETED |
| `REQ-P07-S02-002` | `src/storage/migrations/` | `test_migration_round_trip`, `test_migrations_match_the_models` | Round trip passes on SQLite and PostgreSQL 16 | COMPLETED |
| `REQ-P07-S02-003` | Parametrised test fixture | `DFU_TEST_DATABASE_URL`; CI `postgres` job | Local PostgreSQL 16: all passed. CI awaits a push | IN_PROGRESS |
| `REQ-P07-S02-004` | `scripts/deployment/import_sqlite.py` | `test_import_verifies_counts` | `reports/deployment/p07_s02_import_report.json` | COMPLETED |
| `REQ-P07-S02-005` | `src/api/app.py` | `tests/api/`, `tests/storage/test_database_outage.py` | Smoke test 8/8 with the real model on PostgreSQL | COMPLETED |
