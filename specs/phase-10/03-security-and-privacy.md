# P10-S03 — Security and Privacy Controls

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

## 1. Objective

Apply the privacy and abuse controls that a public image service needs.

## 2. Scope

- Automatic deletion of uploads
- EXIF and metadata removal
- Consent record
- Per-user and per-IP rate limits
- Security headers and CORS
- Threat model and dependency scanning

## 3. Non-Goals

- HIPAA, GDPR or medical device certification claims
- Accepting real patient data
- Penetration testing by a third party

## 4. Requirements

- `REQ-P10-S03-001`: Uploads and artifacts SHALL be deleted automatically after a configured period (default 24 hours), unless the user chose to keep them.
- `REQ-P10-S03-002`: EXIF and other metadata SHALL be removed before storage, and the original bytes SHALL NOT be kept.
- `REQ-P10-S03-003`: Consent SHALL be recorded with text version and time before the first upload.
- `REQ-P10-S03-004`: Rate limits SHALL apply per user and per IP, returning 429 with `Retry-After`.
- `REQ-P10-S03-005`: A threat model SHALL cover upload, storage, auth and queue, with each risk addressed or accepted.
- `REQ-P10-S03-006`: CI SHALL scan dependencies and images, and SHALL fail on critical findings.

## 5. Assumptions

- The service states that it is not for real patient data.
- Legal review of consent text is the owner's decision before any wide launch.

## 6. Dependencies

- `P07-S03`
- `P07-S04`
- `P08-S02`

## 7. Inputs

- Upload pipeline
- Retention settings

## 8. Outputs

- Retention job
- Sanitiser
- Consent table
- Threat model
- Privacy page

## 9. Data / Interface Contract

`DFU_RETENTION_HOURS` sets retention. Sanitising changes file bytes, so the stored hash is taken after sanitising, and pixel values stay unchanged.

## 10. Invariants

- The sanitised file is the only stored copy.
- Deleted data leaves no blob.
- Rate-limit data holds no image content.

## 11. Technical Design

Sanitising re-encodes without metadata; PNG and other lossless formats keep their pixels, while JPEG uses a lossless metadata strip so that results do not shift. Retention runs on a schedule and deletes storage objects before rows, so a failure can be safely re-run.

## 12. Implementation Tasks

1. Add sanitising.
2. Add retention.
3. Add consent.
4. Add rate limits.
5. Write the threat model.
6. Add scanning.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Deletion fails partway | The job retries, and a report flags objects older than the limit |
| Decompression bomb | Rejected by the existing pixel limit |
| Shared IP | Per-user limits apply after sign-in |

## 14. Tests

- GPS-tagged test image
- Retention including blobs
- Limit bursts
- Security headers

## 15. Acceptance Criteria

- No EXIF survives in storage, and no blob outlives its limit plus one job cycle.
- Each threat has a recorded decision.

## 16. Evidence

- Threat model
- Scan report
- Retention log

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
python -m pytest tests/security -q
```

## 18. Risks / Limitations

- Automatic deletion conflicts with longitudinal use, so keeping data needs an explicit choice. Compliance is not claimed.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P10-S03-001` | `src/worker/retention.py` | `test_retention_deletes_all` | Retention log | NOT_STARTED |
| `REQ-P10-S03-002` | `src/preprocessing/sanitise.py` | `test_exif_removed` | Test run | NOT_STARTED |
| `REQ-P10-S03-003` | `src/api/consent.py` | `test_upload_requires_consent` | Test run | NOT_STARTED |
| `REQ-P10-S03-004` | `src/api/limits.py` | `test_rate_limits` | Test run | NOT_STARTED |
| `REQ-P10-S03-005` | `docs/deployment/THREAT_MODEL.md` | Document review | Threat model | NOT_STARTED |
| `REQ-P10-S03-006` | `.github/workflows/ci.yml` | CI job | Scan report | NOT_STARTED |
