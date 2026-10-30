# P07-S04 Security Review Note

Scope: sign-in and per-user data ownership on `/api/v2`. This is a review of the code by its author, not an independent audit or a penetration test.

## Controls in place

- Token algorithms are pinned to RS256 and ES256, and the signing key's algorithm must match.
- A token must carry a valid signature, issuer, audience and expiry, plus a subject.
- JWKS is fetched only over HTTPS, or from a loopback address for tests.
- Tokens are not written to logs.
- A user's identity is `issuer|subject`, so the same subject from another issuer is a different user.
- Every read and write is scoped in the repository, not in individual routes.
- An ID owned by someone else returns 404, the same as an ID that does not exist.
- The `demo` user has no subject, so no token can reach it.
- `/api/v1` and the dashboard are absent when `DFU_AUTH_ISSUER` is set.

## Known limits

- A signed URL is a bearer link. Anyone holding one can use it until it expires: 1 hour for export links, 5 minutes for downloads.
- With the local storage backend, signed URLs may appear in access logs.
- A token that is still valid after account deletion creates a new, empty account. It cannot reach the deleted data.
- Clerk needs a JWT template to set `aud`.
- The cross-user isolation test enumerates routes from OpenAPI, so it does not see `include_in_schema=False` routes. Today the only such router is the signature-checked blob router.

## Verified locally

- SQLite: full suite, 395 passed.
- PostgreSQL 16 (embedded): `tests/storage`, `tests/api` and `tests/worker`, 171 passed.

## Not yet proven

- The CI run. It needs a push.
- Sign-in against a real identity provider. The tests use locally generated keys.
