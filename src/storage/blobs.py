"""P07-S03 blob storage: one interface, local-disk and S3 backends.

Finished objects are content-addressed, ``<sha[:2]>/<sha><suffix>``, so a read
can always recompute the hash (REQ-P07-S03-002) and identical files share one
object.  Clients never get a URL that writes to such a key: a pre-signed upload
lands on ``uploads/<upload_id>`` and is copied to its hash key only after the
server has verified it, so nobody can place other bytes under a known hash.

The bucket stays private (REQ-P07-S03-005).  Credentials come from the standard
``AWS_*`` environment variables and never leave the server.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.storage.database import NotFoundError, StorageError

log = logging.getLogger(__name__)

CONTENT_KEY = re.compile(r"^[0-9a-f]{2}/([0-9a-f]{64})(\.[a-z0-9]+)?$")
STAGING_PREFIX = "uploads/"
PUBLIC_GRANTEES = ("AllUsers", "AuthenticatedUsers")
MEDIA_BY_SUFFIX = {".png": "image/png", ".jpg": "image/jpeg", ".bmp": "image/bmp",
                   ".tif": "image/tiff", ".webp": "image/webp"}


def staging_key(upload_id: str) -> str:
    return f"{STAGING_PREFIX}{upload_id}"


class BlobStore(ABC):
    """``write``/``read`` move raw bytes; ``put``/``get`` add the content addressing."""

    @abstractmethod
    def write(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def read(self, key: str, limit: int | None = None) -> bytes:
        """The object's bytes, unverified, up to ``limit``.  Staged uploads are read this way."""

    @abstractmethod
    def size(self, key: str) -> int: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def presign(self, key: str, method: str = "GET", expires_in: int = 300, content_length: int | None = None) -> str:
        """A URL for one object that stops working after ``expires_in`` seconds."""

    @abstractmethod
    def ping(self) -> bool: ...

    @abstractmethod
    def ensure_private(self) -> None:
        """Raise ``StorageError`` if the store can be read without a signature."""

    def put(self, data: bytes, suffix: str = "") -> tuple[str, str]:
        digest = hashlib.sha256(data).hexdigest()
        key = f"{digest[:2]}/{digest}{suffix}"
        if not self.exists(key):
            self.write(key, data)
        return key, digest

    def get(self, key: str) -> bytes:
        match = CONTENT_KEY.match(key)
        if match is None:
            raise StorageError("BLOB_KEY_INVALID", f"Invalid storage key: {key}")
        data = self.read(key)
        if hashlib.sha256(data).hexdigest() != match.group(1):
            log.error("Blob corruption: stored bytes do not match the hash in key %s", key)
            raise StorageError("BLOB_CORRUPT", f"Stored file failed its hash check: {key}")
        return data


class LocalBlobStore(BlobStore):
    """Files under ``root``.  Signed URLs point at the API's own ``/api/v2/blobs`` routes."""

    def __init__(self, root: str | Path, secret: str | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        # Without a shared secret, URLs are valid only on the process that issued them.
        self._secret = (secret or os.environ.get("DFU_BLOB_URL_SECRET") or secrets.token_hex(32)).encode()

    def path(self, key: str) -> Path:
        resolved = (self.root / key).resolve()
        if self.root.resolve() not in resolved.parents:
            raise StorageError("BLOB_KEY_INVALID", f"Invalid storage key: {key}")
        return resolved

    def write(self, key: str, data: bytes) -> None:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)

    def read(self, key: str, limit: int | None = None) -> bytes:
        path = self.path(key)
        if not path.is_file():
            raise NotFoundError("BLOB_MISSING", f"Stored file is missing: {key}")
        with path.open("rb") as handle:
            return handle.read() if limit is None else handle.read(limit)

    def size(self, key: str) -> int:
        path = self.path(key)
        if not path.is_file():
            raise NotFoundError("BLOB_MISSING", f"Stored file is missing: {key}")
        return path.stat().st_size

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def delete(self, key: str) -> None:
        path = self.path(key)
        if path.exists():
            path.unlink()

    def ping(self) -> bool:
        return self.root.is_dir()

    def ensure_private(self) -> None:
        """Local files are only served through signed routes."""

    def _signature(self, method: str, key: str, expires: int, length: int | None) -> str:
        payload = f"{method}\n{key}\n{expires}\n{length}".encode()
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def presign(self, key: str, method: str = "GET", expires_in: int = 300, content_length: int | None = None) -> str:
        self.path(key)
        expires = int(time.time()) + expires_in
        query = f"expires={expires}&signature={self._signature(method, key, expires, content_length)}"
        if content_length is not None:
            query += f"&length={content_length}"
        return f"/api/v2/blobs/{key}?{query}"

    def signature_valid(self, method: str, key: str, expires: int, length: int | None, signature: str) -> bool:
        return (time.time() <= expires
                and hmac.compare_digest(self._signature(method, key, expires, length), signature))


class S3BlobStore(BlobStore):
    """Any S3-compatible store.  Cloudflare R2 is the default target; MinIO runs in CI."""

    def __init__(self, bucket: str, endpoint_url: str | None = None, client: Any = None) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = client or boto3.client(
            "s3", endpoint_url=endpoint_url,
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=30,
                          retries={"max_attempts": 2}))

    @contextmanager
    def _errors(self, key: str) -> Iterator[None]:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            yield
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                raise NotFoundError("BLOB_MISSING", f"Stored file is missing: {key}") from error
            log.exception("Object storage request failed")
            raise StorageError("STORAGE_UNAVAILABLE", "Object storage is unavailable") from error
        except BotoCoreError as error:
            log.exception("Object storage request failed")
            raise StorageError("STORAGE_UNAVAILABLE", "Object storage is unavailable") from error

    def write(self, key: str, data: bytes) -> None:
        with self._errors(key):
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def read(self, key: str, limit: int | None = None) -> bytes:
        options = {} if limit is None else {"Range": f"bytes=0-{limit - 1}"}
        with self._errors(key):
            return self.client.get_object(Bucket=self.bucket, Key=key, **options)["Body"].read()

    def size(self, key: str) -> int:
        with self._errors(key):
            return int(self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])

    def exists(self, key: str) -> bool:
        try:
            self.size(key)
        except NotFoundError:
            return False
        return True

    def delete(self, key: str) -> None:
        with self._errors(key):
            self.client.delete_object(Bucket=self.bucket, Key=key)

    def ping(self) -> bool:
        with self._errors(self.bucket):
            self.client.head_bucket(Bucket=self.bucket)
        return True

    def presign(self, key: str, method: str = "GET", expires_in: int = 300, content_length: int | None = None) -> str:
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if content_length is not None:
            params["ContentLength"] = content_length  # signed, so a different length is refused
        with self._errors(key):
            return self.client.generate_presigned_url("get_object" if method == "GET" else "put_object",
                                                       Params=params, ExpiresIn=expires_in)

    def ensure_private(self) -> None:
        from botocore.exceptions import ClientError

        with self._errors(self.bucket):
            try:
                self.client.put_public_access_block(Bucket=self.bucket, PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True, "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != "NotImplemented":  # R2 has no such API
                    raise
            try:
                grants = self.client.get_bucket_acl(Bucket=self.bucket)["Grants"]
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != "NotImplemented":
                    raise
                return
        public = [grant for grant in grants if str(grant.get("Grantee", {}).get("URI", "")).endswith(PUBLIC_GRANTEES)]
        if public:
            raise StorageError("BUCKET_PUBLIC", f"Bucket {self.bucket} is readable without a signature")


def create_blob_store(backend: str, data_dir: Path, bucket: str | None = None,
                      endpoint_url: str | None = None) -> BlobStore:
    if backend == "local":
        return LocalBlobStore(data_dir / "blobs")
    if backend == "s3":
        if not bucket:
            raise StorageError("STORAGE_NOT_CONFIGURED", "DFU_S3_BUCKET is required when DFU_STORAGE_BACKEND=s3")
        return S3BlobStore(bucket, endpoint_url)
    raise StorageError("STORAGE_NOT_CONFIGURED", f"Unknown DFU_STORAGE_BACKEND: {backend}")
