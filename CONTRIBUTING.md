# Contributing

This project is spec-driven. A change is finished when its requirement, test and evidence all agree, not when the
code runs.

1. **Start from a spec.** New work needs an approved specification in `specs/`, written from
   `specs/SPEC_TEMPLATE.md`. Small fixes that change no behaviour do not need one.
2. **Keep the tests green.** Run `python -m pytest -q` and `ruff check .` before committing.
3. **Record the evidence.** Update `specs/TRACEABILITY.md`, `specs/MASTER_TRACKER.md` and `CHANGELOG.md`. Status
   values and the Definition of Done are in `specs/conventions.md`.

## Rules that do not bend

- Never tune on a test or external set. Report a held-out result once.
- Keep hypotheses separate from measured results.
- Never add diagnostic or treatment wording. Results are image-derived technical measurements.
- Keep the external result (LowerLimb Dice 0.26) and the medical notice visible.
- Never commit datasets, checkpoints, credentials or real patient data.

Setup, layout and commands are in the [development guide](docs/development/DEVELOPMENT.md).
