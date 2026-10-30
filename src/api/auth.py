"""P07-S04 token verification.

The sign-in provider holds the passwords.  This service only checks the JWT it
issued against the provider's published keys (REQ-P07-S04-003) and then scopes
the repository to that user, so a v2 route never sees an unscoped repository.

Only standard OIDC and JWT rules are used, so any provider that publishes a
JWKS document works.  No token value is ever put in an error or a log line.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import jwt
from fastapi import Header
from jwt import PyJWK

from src.api.errors import ApiError
from src.api.service import ApiSettings, ServiceState
from src.storage.repository import Repository

# Asymmetric only: accepting HS256 would let the public key be used as a shared secret.
SIGNING_ALGORITHMS = ("RS256", "ES256")
REQUIRED_CLAIMS = ["exp", "iss", "aud", "sub"]
LEEWAY_SECONDS = 30
JWKS_TTL_SECONDS = 3600
JWKS_RETRY_SECONDS = 30  # an unknown key ID in a forged token cannot flood the provider
JWKS_TIMEOUT_SECONDS = 5
JWKS_MAX_BYTES = 1024 * 1024
log = logging.getLogger("dfu.api")


def _rejected(code: str = "TOKEN_INVALID", message: str = "The access token is not valid") -> ApiError:
    return ApiError("UNAUTHENTICATED", code, message)


def fetch_jwks(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=JWKS_TIMEOUT_SECONDS) as response:  # noqa: S310 - scheme checked below
        return json.loads(response.read(JWKS_MAX_BYTES))


class JwksCache:
    """Provider keys by key ID.  An outage keeps the old keys working."""

    def __init__(self, url: str, fetch: Callable[[str], dict[str, Any]] = fetch_jwks,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.url, self._fetch, self._clock = url, fetch, clock
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at: float | None = None
        self._tried_at: float | None = None
        self._reachable = True
        self._lock = threading.Lock()

    def _refresh(self) -> None:
        with self._lock:
            now = self._clock()
            if self._tried_at is not None and now - self._tried_at < JWKS_RETRY_SECONDS:
                return
            self._tried_at = now
            try:
                document = self._fetch(self.url)
                keys = {}
                for entry in document["keys"]:
                    try:
                        keys[entry["kid"]] = PyJWK.from_dict(entry)
                    except (jwt.PyJWTError, KeyError):
                        continue  # a key this service cannot use, such as an encryption key
            except (OSError, ValueError, KeyError, TypeError):
                self._reachable = False
                log.warning("Could not refresh the sign-in provider's keys")
                return
            self._keys, self._fetched_at, self._reachable = keys, now, True

    def key(self, key_id: str) -> PyJWK:
        expired = self._fetched_at is None or self._clock() - self._fetched_at >= JWKS_TTL_SECONDS
        if key_id not in self._keys or expired:
            self._refresh()
        if key_id in self._keys:
            return self._keys[key_id]
        if not self._reachable or not self._keys:
            raise ApiError("INFRASTRUCTURE_FAILURE", "AUTH_PROVIDER_UNAVAILABLE",
                           "The sign-in provider's keys are not available")
        raise _rejected()


class TokenVerifier:
    def __init__(self, issuer: str, audience: str, keys: JwksCache) -> None:
        self.issuer, self.audience, self.keys = issuer, audience, keys

    def subject(self, token: str) -> str:
        """The account a valid token belongs to.  Issuer is included, so providers cannot collide."""

        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise _rejected() from error
        algorithm, key_id = header.get("alg"), header.get("kid")
        if algorithm not in SIGNING_ALGORITHMS or not isinstance(key_id, str):
            raise _rejected()
        key = self.keys.key(key_id)
        if key.algorithm_name != algorithm:
            raise _rejected()
        try:
            claims = jwt.decode(token, key.key, algorithms=[algorithm], audience=self.audience, issuer=self.issuer,
                                leeway=LEEWAY_SECONDS, options={"require": REQUIRED_CLAIMS})
        except jwt.ExpiredSignatureError as error:
            raise _rejected("TOKEN_EXPIRED", "The access token has expired") from error
        except jwt.PyJWTError as error:
            raise _rejected() from error
        if not claims["sub"]:
            raise _rejected()
        return f"{self.issuer}|{claims['sub']}"


def build_verifier(settings: ApiSettings) -> TokenVerifier | None:
    """``None`` means v2 answers 503.  A half-configured service stays closed."""

    if not settings.auth_issuer or not settings.auth_audience:
        return None
    url = settings.auth_jwks_url or f"{settings.auth_issuer.rstrip('/')}/.well-known/jwks.json"
    parts = urlsplit(url)
    if parts.scheme != "https" and parts.hostname not in ("127.0.0.1", "localhost"):
        log.error("Refusing a sign-in key URL that is not HTTPS")
        return None
    return TokenVerifier(settings.auth_issuer, settings.auth_audience, JwksCache(url))


def user_repository(state: ServiceState, verifier: TokenVerifier | None) -> Callable[..., Repository]:
    """The FastAPI dependency behind every private v2 route (REQ-P07-S04-001)."""

    def current_repository(authorization: str | None = Header(default=None)) -> Repository:
        if verifier is None:
            raise ApiError("INFRASTRUCTURE_FAILURE", "AUTH_NOT_CONFIGURED", "User accounts are not configured")
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise _rejected("TOKEN_MISSING", "This route needs an access token")
        return state.db.for_owner(state.db.ensure_user(verifier.subject(token.strip())))

    return current_repository
