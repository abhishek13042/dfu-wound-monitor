"""P07-S03: moving existing blobs verifies every hash and leaves the source alone."""

from __future__ import annotations

from scripts.deployment.migrate_blobs import migrate_blobs
from src.storage.blobs import LocalBlobStore


def test_every_blob_arrives_verified(tmp_path, s3_store):
    source = LocalBlobStore(tmp_path / "blobs")
    keys = [source.put(f"file {n}".encode(), ".png")[0] for n in range(3)]
    source.write("uploads/upl-1", b"staged, not part of the record")
    report = migrate_blobs(source, s3_store, verify=True)
    assert report == {"files": 3, "copied": 3, "already_present": 0, "verified": 3, "failures": []}
    assert all(s3_store.exists(key) for key in keys)
    assert not s3_store.exists("uploads/upl-1")
    assert all(source.exists(key) for key in keys)


def test_running_again_copies_nothing(tmp_path, s3_store):
    source = LocalBlobStore(tmp_path / "blobs")
    source.put(b"data", ".png")
    migrate_blobs(source, s3_store)
    report = migrate_blobs(source, s3_store, verify=True)
    assert (report["copied"], report["already_present"], report["verified"]) == (0, 1, 1)


def test_corrupt_source_file_is_reported_and_not_copied(tmp_path, s3_store):
    source = LocalBlobStore(tmp_path / "blobs")
    key, _ = source.put(b"good", ".png")
    source.write(key, b"bad")
    report = migrate_blobs(source, s3_store, verify=True)
    assert report["failures"] == [{"key": key, "reason": "BLOB_CORRUPT"}]
    assert not s3_store.exists(key)


def test_file_without_a_hash_name_is_reported(tmp_path, s3_store):
    source = LocalBlobStore(tmp_path / "blobs")
    source.write("ab/notes.txt", b"stray")
    report = migrate_blobs(source, s3_store)
    assert report["failures"] == [{"key": "ab/notes.txt", "reason": "NOT_CONTENT_ADDRESSED"}]
