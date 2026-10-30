"""P07-S03: both backends must pass the same tests (REQ-P07-S03-001)."""

from __future__ import annotations

import hashlib
import os
import time
import urllib.error
import urllib.request

import pytest

from src.storage.blobs import LocalBlobStore, S3BlobStore, create_blob_store, staging_key
from src.storage.database import NotFoundError, StorageError


@pytest.fixture(params=["local", "s3"])
def store(request, tmp_path):
    if request.param == "local":
        return LocalBlobStore(tmp_path / "blobs", secret="test")
    return request.getfixturevalue("s3_store")


def test_put_get_round_trip_is_content_addressed(store):
    key, digest = store.put(b"wound image", ".png")
    assert digest == hashlib.sha256(b"wound image").hexdigest()
    assert key == f"{digest[:2]}/{digest}.png"
    assert store.get(key) == b"wound image"
    assert store.size(key) == 11


def test_identical_content_shares_one_object(store):
    assert store.put(b"same", ".png") == store.put(b"same", ".png")


def test_exists_and_delete(store):
    key, _ = store.put(b"data")
    assert store.exists(key)
    store.delete(key)
    assert not store.exists(key)
    store.delete(key)  # deleting twice is not an error


def test_missing_blob_is_not_found(store):
    key = f"ab/{'ab' * 32}.png"
    with pytest.raises(NotFoundError) as error:
        store.get(key)
    assert error.value.code == "BLOB_MISSING"
    with pytest.raises(NotFoundError):
        store.size(key)


def test_corrupt_blob_detected(store, caplog):
    key, _ = store.put(b"original", ".png")
    store.write(key, b"tampered")
    with pytest.raises(StorageError) as error:
        store.get(key)
    assert error.value.code == "BLOB_CORRUPT"
    assert "corruption" in caplog.text


def test_get_refuses_a_key_with_no_hash(store):
    store.write(staging_key("upl-1"), b"unverified")
    with pytest.raises(StorageError) as error:
        store.get(staging_key("upl-1"))
    assert error.value.code == "BLOB_KEY_INVALID"


def test_read_can_stop_at_a_limit(store):
    store.write(staging_key("upl-2"), b"0123456789")
    assert store.read(staging_key("upl-2"), limit=4) == b"0123"
    assert store.read(staging_key("upl-2")) == b"0123456789"


def test_ping(store):
    assert store.ping()


def test_store_is_private(store):
    store.ensure_private()


def test_unknown_backend_is_refused(tmp_path):
    with pytest.raises(StorageError) as error:
        create_blob_store("floppy", tmp_path)
    assert error.value.code == "STORAGE_NOT_CONFIGURED"
    with pytest.raises(StorageError):
        create_blob_store("s3", tmp_path)


def test_local_key_cannot_leave_the_root(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    with pytest.raises(StorageError) as error:
        store.read("../outside.txt")
    assert error.value.code == "BLOB_KEY_INVALID"


def test_local_signature_binds_method_key_length_and_time(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs", secret="test")
    url = store.presign("uploads/upl-1", "PUT", 60, 100)
    fields = dict(item.split("=") for item in url.split("?")[1].split("&"))
    expires, signature = int(fields["expires"]), fields["signature"]
    assert store.signature_valid("PUT", "uploads/upl-1", expires, 100, signature)
    assert not store.signature_valid("GET", "uploads/upl-1", expires, 100, signature)
    assert not store.signature_valid("PUT", "uploads/upl-2", expires, 100, signature)
    assert not store.signature_valid("PUT", "uploads/upl-1", expires, 101, signature)
    assert not store.signature_valid("PUT", "uploads/upl-1", expires + 1, 100, signature)
    assert not store.signature_valid("PUT", "uploads/upl-1", int(time.time()) - 1, 100, signature)


def test_s3_presigned_get_works_and_plain_url_does_not(s3_store):
    key, _ = s3_store.put(b"private bytes", ".png")
    signed = s3_store.presign(key, "GET", 60)
    with urllib.request.urlopen(signed, timeout=30) as response:
        assert response.read() == b"private bytes"
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(signed.split("?")[0], timeout=30)
    assert error.value.code == 403


def test_s3_upload_url_signs_the_length(s3_store):
    url = s3_store.presign(staging_key("upl-3"), "PUT", 600, 1234)
    assert "X-Amz-Signature=" in url
    assert "content-length" in url.split("X-Amz-SignedHeaders=")[1].split("&")[0]


@pytest.mark.skipif(bool(os.environ.get("DFU_TEST_S3_ENDPOINT")), reason="MinIO has no public bucket ACL to detect")
def test_public_bucket_is_detected(s3_store):
    s3_store.client.put_bucket_acl(Bucket=s3_store.bucket, ACL="public-read")
    original = s3_store.client.put_public_access_block
    s3_store.client.put_public_access_block = lambda **_: None
    try:
        with pytest.raises(StorageError) as error:
            s3_store.ensure_private()
    finally:
        s3_store.client.put_public_access_block = original
    assert error.value.code == "BUCKET_PUBLIC"


def test_unreachable_storage_is_an_infrastructure_error():
    import boto3
    from botocore.config import Config

    client = boto3.client("s3", endpoint_url="http://127.0.0.1:1", region_name="us-east-1",
                          aws_access_key_id="x", aws_secret_access_key="x",
                          config=Config(connect_timeout=1, retries={"max_attempts": 1}))
    store = S3BlobStore("bucket", client=client)
    with pytest.raises(StorageError) as error:
        store.write("ab/key", b"data")
    assert error.value.code == "STORAGE_UNAVAILABLE"
    assert "127.0.0.1" not in error.value.message
