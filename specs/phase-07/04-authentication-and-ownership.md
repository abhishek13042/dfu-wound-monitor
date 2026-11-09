# P07-S04 — Authentication and Data Ownership

**Status:** `COMPLETED`. Every requirement and acceptance criterion is met on SQLite and PostgreSQL, locally and in CI (run 42478962863, 2026-11-08). A live provider tenant has not been tried; that is the owner's deployment step (see §18). Anonymous sample images move to P08-S02, because samples must be synthetic or licensed.

## 1. Objective

Give each user a private workspace through a managed sign-in provider, without storing passwords.

## 2. Scope

- JWT verification against the provider's public keys
- `users` table and `owner_id` on cases
- Ownership checks on every route
- Anonymous sample-image access (moved to P08-S02, because samples must be synthetic or licensed)
- User data export and account deletion

## 3. Non-Goals

- Organisations, teams or sharing
- Self-stored passwords
- Clinical role models or any patient-record compliance claim

## 4. Requirements

- `REQ-P07-S04-001`: Every `/api/v2` route, other than public model info and samples, SHALL require a valid token.
- `REQ-P07-S04-002`: A user SHALL NOT read, change or delete another user's data. A foreign ID SHALL return 404.
- `REQ-P07-S04-003`: The service SHALL verify token signature, issuer, audience and expiry, and SHALL NOT store passwords.
- `REQ-P07-S04-004`: A user SHALL be able to export their data and delete their account, and deletion SHALL remove their rows and blobs.
- `REQ-P07-S04-005`: Existing data SHALL be assigned to a `demo` owner by migration, without loss.

## 5. Assumptions

- Clerk is the default provider. The code depends only on standard OIDC and JWT rules, so Supabase Auth can replace it.
- The owner creates the provider account and supplies its keys through the environment.

## 6. Dependencies

- `P07-S02`

## 7. Inputs

- `DFU_AUTH_ISSUER`, `DFU_AUTH_AUDIENCE`, provider JWKS URL

## 8. Outputs

- `src/api/auth.py`
- `src/api/account.py`
- `users` table and migration

## 9. Data / Interface Contract

Clients send `Authorization: Bearer <token>`. New error category `UNAUTHENTICATED` maps to 401, with failure class `INPUT`. Every case carries `owner_id`, and the repository takes the user as an argument, so an unscoped query cannot be written by accident.

## 10. Invariants

- Authorisation is enforced in the repository, not only in routes.
- Tokens never appear in logs.
- `/api/v1` is disabled wherever real user accounts are enabled, because it has no authentication.

## 11. Technical Design

A FastAPI dependency verifies the token and loads or creates the `users` row. JWKS keys are cached and refreshed when an unknown key ID appears. Returning 404 for foreign IDs avoids revealing that they exist.

## 12. Implementation Tasks

1. Add token verification with a test signing key.
2. Add the owner column and migration.
3. Scope every repository call.
4. Add export and deletion.
5. Write the isolation test over all routes.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Expired token | 401 `UNAUTHENTICATED` |
| Provider key endpoint down | Cached keys are used; with no cached key, 503 |
| User deleted while a job runs | The job stops and stores nothing |

## 14. Tests

- Forged, expired and wrong-audience tokens
- Cross-user access for every route
- Complete deletion, including blobs

## 15. Acceptance Criteria

- The isolation test covers every `/api/v2` route, enforced by a test that lists the routes.
- No password or token is stored or logged.

## 16. Evidence

- Recorded on 2026-11-08. [Actions run 42478962863](https://github.com/abhishek13042/dfu-wound-monitor/actions/runs/42478962863) on [PR #1](https://github.com/abhishek13042/dfu-wound-monitor/pull/1), commit `7b1d999`. `test_owner_migration` and the isolation tests ran in the `postgres` and `quality` jobs.
- Test report
- Security review note

## 17. Reproducibility

```bash
python -m pytest tests/api/test_auth.py -q
```

## 18. Risks / Limitations

- A provider outage blocks sign-in.
- Tested against a fake OIDC provider that signs real RS256 tokens, not a live Clerk tenant. Creating the tenant and its keys is the owner's deployment step.
- Free-tier user limits may change.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P07-S04-001` | `src/api/auth.py` | `tests/api/test_auth.py` | Test run | COMPLETED |
| `REQ-P07-S04-002` | Repository owner filter | `test_cross_user_isolation`, for every route | Test run | COMPLETED |
| `REQ-P07-S04-003` | `src/api/auth.py` | `test_rejects_bad_tokens` | `reports/deployment/p07_s04_security_review.md` | COMPLETED |
| `REQ-P07-S04-004` | `src/api/account.py` | `test_account_deletion_is_complete` | Test run | COMPLETED |
| `REQ-P07-S04-005` | Alembic revision | `test_owner_migration` | Passes on SQLite and PostgreSQL 16 locally, and in Actions run 42478962863: `postgres` job | COMPLETED |
