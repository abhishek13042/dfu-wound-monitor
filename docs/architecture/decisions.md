# Design decisions

Each entry records a decision that shapes the code and the reason for it. New decisions go at the end. Replace a
decision by adding an entry that supersedes it, so the history stays readable.

| # | Decision | Reason | Where |
|---|---|---|---|
| 1 | Work is spec-driven, with requirement IDs traced to tests and evidence | Results must be checkable, and code alone does not prove a requirement is met | `specs/` |
| 2 | Full-image segmentation is the default; a detector is optional | Evidence has not shown that a localisation stage is needed | `specs/REVISED_ROADMAP.md` |
| 3 | ResNet34 U-Net at 512 px with an ImageNet-pretrained encoder | The lightweight baseline was too weak, and FUSeg2021 is a small dataset | `specs/phase-02/SPEC-02-03-strong-segmentation.md` |
| 4 | Official FUSeg validation became the held-out test set | The public test split has no masks, so it cannot produce a score | `data/README.md` |
| 5 | Threshold and minimum area are tuned on internal validation only | Tuning on the test set would inflate the result | `reports/experiments/spec_02_03_report.md` |
| 6 | LowerLimb V3 is used without any tuning | An external check loses its meaning if it is tuned | `reports/final/phase_06_validation_report.md` |
| 7 | Checkpoints are pinned by SHA-256 and refused on mismatch | A wrong model must fail loudly at startup | `src/inference/engine.py` |
| 8 | The quality gate runs before the model, and rejection skips inference | Bad photos must not produce confident measurements | `src/inference/pipeline.py` |
| 9 | Measurements stay in pixels unless a scale is supplied | No dataset has a reliable physical scale, and a guessed one would be false precision | `src/measurement/engine.py` |
| 10 | Case identity is explicit and never inferred from filenames | Silent identity guesses would produce false trends | `src/longitudinal/records.py` |
| 11 | Comparisons use an explicit compatibility policy | Different models or calibrations must not be compared as if they matched | `src/longitudinal/comparison.py` |
| 12 | SQLite plus a content-addressed blob store | Enough for one machine, with migrations and no external service. Superseded for shared deployments by decision 12a | `src/storage/database.py` |
| 12b | S3-compatible blobs behind one `BlobStore` interface, with direct uploads through signed URLs | Instances share no disk, image bytes stay off the API, and the store enforces the size limit | `src/storage/blobs.py` |
| 12a | PostgreSQL through SQLAlchemy and Alembic; SQLite kept for local use | Several API and worker instances need one database, and PostgreSQL is the authority when the two differ | `src/storage/repository.py` |
| 13 | The dashboard uses only the public API | The interface can then be replaced without touching model code | `src/dashboard/index.html` |
| 14 | Five failure classes in one error body | Clients must tell a bad photo from a broken model | `src/api/app.py` |
| 15 | No optimisation without a measured need | The benchmark recorded the bottleneck, and no latency requirement existed | `reports/final/p06_benchmark.json` |
| 16 | The checkpoint is fetched at container start from a Hugging Face repo | It is too large for git, and the hash check still applies | `scripts/deployment/fetch_checkpoint.py` |
| 17 | Sign-in is delegated to a provider through standard JWT checks | No passwords are stored, and the provider can change without code changes | `src/api/auth.py` |
| 18 | Ownership is enforced in the repository, and foreign IDs return 404 | A route cannot forget the check, and a response cannot reveal that an ID exists | `src/storage/repository.py` |
| 19 | arq on Redis, with the database row as the source of truth | A message can be lost or delivered twice, so a conditional claim on the row gives idempotency | `src/worker/tasks.py` |
| 20 | The API holds no model when a queue is configured | API instances stay small, and workers scale on their own | `src/api/app.py` |
| 21 | The API row is written before the message is sent, and removed if sending fails | A job can never be queued with no row, and a failed submit leaves no orphan | `src/api/analyses_v2.py` |
