# Specification Conventions & Standards

## 1. Identifier Conventions

### Specification IDs
Specifications follow the format:
`PXX-SXX`

- `PXX`: Two-digit phase identifier (e.g., `P00`, `P01`, `P02`).
- `SXX`: Two-digit sequential specification identifier within that phase (e.g., `S01`, `S02`).

*Example:* `P01-S03` denotes **Phase 01, Specification 03**.

#### Consolidated specification IDs (Phase 02 exception)
Phase 02 uses two consolidated execution specifications, `SPEC-02-01` and
`SPEC-02-02`, in the form `SPEC-PP-NN`.

- `SPEC-02-01` implements P02-S01 to P02-S03 on real data.
- `SPEC-02-02` absorbs P02-S04 to P02-S07.

Their requirements use `REQ-SPEC-02-0N-XXX`. The granular `P02-SXX` IDs remain
valid for traceability. All phases from Phase 03 onward use `PXX-SXX` again.

### Requirement IDs
Requirements within specifications follow the format:
`REQ-PXX-SXX-XXX`

- `PXX`: Two-digit phase identifier.
- `SXX`: Two-digit specification identifier.
- `XXX`: Three-digit requirement counter (e.g., `001`, `002`).

*Example:* `REQ-P02-S01-004` denotes **Phase 02, Specification 01, Requirement 004**.

---

## 2. Status Taxonomy

Only the following status values are permitted across trackers and specifications:

- `NOT_STARTED`: Specification or requirement has been authored/planned but work has not begun.
- `IN_PROGRESS`: Specification is currently under active design or implementation.
- `BLOCKED`: Work cannot proceed due to unmet dependencies, environment issues, or open questions.
- `FAILED`: Tests or acceptance criteria failed to meet target benchmarks or invariants.
- `COMPLETED`: All requirements, tests, evidence, and acceptance criteria are fulfilled per the Definition of Done.
- `DEFERRED`: Explicitly postponed to a future phase or milestone.

---

## 3. Definition of Done (DoD)

A specification is marked **`COMPLETED`** if and only if all of the following conditions are satisfied:

1. **Requirements Implemented**: All specified functional and non-functional requirements are completely implemented.
2. **Tests Passing**: All unit, integration, and domain-specific tests associated with the specification execute and pass cleanly.
3. **Acceptance Criteria Satisfied**: Explicit acceptance criteria defined in the specification are objectively verified.
4. **Evidence Generated**: Verifiable evidence (test outputs, execution logs, benchmark reports, visualizations) is recorded in designated directories.
5. **Reproducibility Documented**: Precise commands, environment settings, seeds, configurations, and artifact paths are documented.
6. **Limitations & Risks Recorded**: Any assumptions, boundary conditions, edge cases, or known limitations are clearly documented.

> **CRITICAL RULE:**  
> *"Code exists" does NOT mean "specification completed."* No specification may be marked `COMPLETED` without corresponding verification tests and documented evidence.

