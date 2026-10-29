# Database (reserved)

Persistence is implemented in `src/storage/database.py`: SQLite with versioned schema migrations, plus a
content-addressed blob store for images and masks (P05-S02, `specs/phase-05/02-persistence-and-results.md`).

This folder is reserved for the planned PostgreSQL + Alembic migration (Phase 07, step B in
`docs/roadmap/PRODUCTION_ROADMAP.md`). Its subfolders (`migrations/`, `schemas/`, `seeds/`) are empty until
that specification is approved.
