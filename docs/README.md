# Documentation index

Start with the [project README](../README.md). The notice there applies to every document: this is a research
prototype, not a medical device.

## Understand the system

| Document | What it covers |
|---|---|
| [System architecture](architecture/system-architecture.md) | Components, request flow, pipeline stages, invariants |
| [Design decisions](architecture/decisions.md) | Why the main technical choices were made |
| [Model card](deployment/MODEL_CARD.md) | Model, training data, results, limitations |
| [Data guide](../data/README.md) | Datasets, manifests, splits, data policies |

## Use and run it

| Document | What it covers |
|---|---|
| [Release guide](release/RELEASE.md) | Install, checkpoint, start, health checks, smoke test, release checklist |
| [API reference](api/API.md) | Endpoints, upload fields, error format, environment variables |
| [Hugging Face deployment](deployment/HUGGINGFACE.md) | Docker image and Space publishing steps |
| [Docker notes](../docker/README.md) | Files in the production image |

## Work on it

| Document | What it covers |
|---|---|
| [Contributing](../CONTRIBUTING.md) | The rules for a change, from spec to evidence |
| [Development guide](development/DEVELOPMENT.md) | Setup, repository layout, commands, code style |
| [Testing guide](development/TESTING.md) | Test suites, fixtures, what tests do and do not prove |
| [Experiment records](development/EXPERIMENTS.md) | What every training or evaluation run must record |
| [Scripts guide](../scripts/README.md) | Every script, grouped by purpose |

## Requirements and plans

| Document | What it covers |
|---|---|
| [Master tracker](../specs/MASTER_TRACKER.md) | Status of every phase and specification |
| [Traceability matrix](../specs/TRACEABILITY.md) | Requirement to code, test and evidence |
| [Revised roadmap](../specs/REVISED_ROADMAP.md) | Phase structure and dependency order |
| [Production roadmap](roadmap/PRODUCTION_ROADMAP.md) | Target platform for Phases 07–10 |
| [Spec template](../specs/SPEC_TEMPLATE.md) and [conventions](../specs/conventions.md) | How specifications are written and closed |

## Evidence

| Document | What it covers |
|---|---|
| [Segmentation report](../reports/experiments/spec_02_03_report.md) | Training and held-out results |
| [Phase 06 validation report](../reports/final/phase_06_validation_report.md) | End-to-end and external validation |
| [Release manifest](../reports/final/release_manifest.json) | Versions, config hashes, commit and evidence files |
| [Changelog](../CHANGELOG.md) | Release history |
