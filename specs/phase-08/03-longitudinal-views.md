# P08-S03 — Longitudinal Views

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

## 1. Objective

Show how a wound's measurements change across examinations, with honest handling of gaps and incompatible records.

## 2. Scope

- Examination timeline
- Recharts trend chart
- Side-by-side and slider comparison
- Display of excluded examinations and reasons

## 3. Non-Goals

- Healing predictions or clinical interpretation
- Image registration between visits
- Reports for clinical use

## 4. Requirements

- `REQ-P08-S03-001`: The trend chart SHALL use only the `/trend` output and SHALL NOT recompute change on the client.
- `REQ-P08-S03-002`: Excluded examinations SHALL be listed with their reason codes, not hidden.
- `REQ-P08-S03-003`: Pixel and calibrated series SHALL NOT share an axis, and a chart with fewer than two valid points SHALL say so.
- `REQ-P08-S03-004`: Every trend view SHALL state that it shows image-derived technical trends, not healing assessment.
- `REQ-P08-S03-005`: Pairwise comparison SHALL show the compatibility result from the API, including warnings.

## 5. Assumptions

- Demonstrations use constructed series, clearly labelled, because no real longitudinal dataset is available.

## 6. Dependencies

- `P08-S02`
- `P04-S03`

## 7. Inputs

- `GET /cases/{id}/trend`
- `GET /compare`

## 8. Outputs

- Timeline, trend and comparison screens

## 9. Data / Interface Contract

The existing trend and comparison responses from Phase 04 are served under `/api/v2` with the same fields.

## 10. Invariants

- No wording suggests healing, deterioration or treatment.
- Constructed demo data is always labelled.
- Missing visits stay visible as gaps.

## 11. Technical Design

Time is the x-axis with true spacing, so uneven visits do not look regular. Comparison uses an image slider. Neither view claims that two photos are aligned.

## 12. Implementation Tasks

1. Add v2 trend routes.
2. Build the timeline.
3. Build the chart.
4. Build the comparison.
5. Add the language checks.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Only one examination | Show a single point and explain that two are needed |
| Mixed model versions | Show the API's compatibility warning |
| Calibration changes midway | Separate the series |

## 14. Tests

- Component tests with exclusions
- A language test for forbidden clinical terms
- Chart states at one, two and many points

## 15. Acceptance Criteria

- A constructed series shows correct values, gaps and exclusions.
- The forbidden-wording test passes on all strings.

## 16. Evidence

- Playwright report
- Screenshots

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
cd web && npx playwright test e2e/longitudinal.spec.ts
```

## 18. Risks / Limitations

- Charts can imply precision or clinical meaning that the data does not support. Accuracy on real series remains unknown.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P08-S03-001` | `web/components/TrendChart.tsx` | Component test | Test report | NOT_STARTED |
| `REQ-P08-S03-002` | `web/components/Exclusions.tsx` | Component test | Test report | NOT_STARTED |
| `REQ-P08-S03-003` | `web/components/TrendChart.tsx` | Component test | Test report | NOT_STARTED |
| `REQ-P08-S03-004` | `web/components/TrendNotice.tsx` | Playwright check | Test report | NOT_STARTED |
| `REQ-P08-S03-005` | `web/components/Compare.tsx` | Component test | Test report | NOT_STARTED |
