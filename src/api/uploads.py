"""P07-S03 pre-signed uploads and downloads.

Flow: ``POST /api/v2/uploads`` issues a URL, the client PUTs the file, ``POST
/api/v2/uploads/{id}/verify`` checks what actually arrived, and only then may an
analysis use it.  The client's size, hash and filename are claims, and nothing
it says about the file type is consulted (REQ-P07-S03-004).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from src.api.analysis_flow import FORMAT_SUFFIX
from src.api.errors import ApiError
from src.api.schemas import API_V2
from src.api.service import ServiceState
from src.inference.errors import InputError, InputTooLargeError
from src.longitudinal.records import new_id
from src.preprocessing.decode import decode_image
from src.storage.blobs import MEDIA_BY_SUFFIX, LocalBlobStore, staging_key
from src.storage.database import NotFoundError
from src.storage.repository import Repository

UPLOAD_URL_SECONDS = 600     # REQ-P07-S03-003: the URL lasts less than the 15 minute limit
UPLOAD_ROW_SECONDS = 900     # leaves time to call verify just after a slow PUT
VERIFIED_ROW_SECONDS = 3600  # an unused verified image is not kept for long
DOWNLOAD_URL_SECONDS = 300
ARTIFACT_KINDS = {"mask": "MASK", "probability": "PROBABILITY"}


class _V2Response(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_version: str = API_V2


class UploadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class UploadResponse(_V2Response):
    upload_id: str
    url: str
    expires_at: datetime


class UploadStatusResponse(_V2Response):
    upload_id: str
    status: str
    format: str | None = None
    expires_at: datetime


class SignedUrlResponse(_V2Response):
    url: str
    expires_at: datetime


def _timestamp(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _reject(state: ServiceState, db: Repository, upload_id: str, error: ApiError) -> ApiError:
    state.blobs.delete(staging_key(upload_id))
    db.finish_upload(upload_id, "REJECTED")
    return error


def verify_upload(state: ServiceState, db: Repository, upload: dict) -> dict:
    """Check the stored object, then move it to its content address."""

    upload_id = upload["upload_id"]
    key = staging_key(upload_id)
    limit = min(upload["declared_size"], state.settings.max_upload_bytes)
    try:
        size = state.blobs.size(key)
    except NotFoundError as error:
        raise ApiError("CONFLICT", "UPLOAD_NOT_RECEIVED", "No file has been uploaded for this ID") from error
    if size > limit:
        raise _reject(state, db, upload_id, ApiError("INVALID_INPUT", "INPUT_TOO_LARGE",
                                                     f"Stored file has {size} bytes, more than the {limit} allowed",
                                                     status=413))
    if size < upload["declared_size"]:
        raise _reject(state, db, upload_id, ApiError("INVALID_INPUT", "UPLOAD_SIZE_MISMATCH",
                                                     f"Stored file has {size} bytes, not {upload['declared_size']}"))
    data = state.blobs.read(key)
    if hashlib.sha256(data).hexdigest() != upload["declared_sha256"]:
        raise _reject(state, db, upload_id, ApiError("INVALID_INPUT", "UPLOAD_HASH_MISMATCH",
                                                     "Stored file does not match the declared SHA-256"))
    try:
        decoded = decode_image(data)
    except InputTooLargeError as error:
        raise _reject(state, db, upload_id, ApiError("INVALID_INPUT", error.code, error.message, error.details,
                                                     status=413)) from error
    except InputError as error:
        raise _reject(state, db, upload_id, ApiError("INVALID_INPUT", error.code, error.message,
                                                     error.details)) from error
    final_key, _ = state.blobs.put(data, FORMAT_SUFFIX.get(decoded.source_format, ""))
    verified = db.finish_upload(upload_id, "VERIFIED", storage_key=final_key, format=decoded.source_format,
                                expires_at=_timestamp(VERIFIED_ROW_SECONDS).isoformat())
    state.blobs.delete(key)
    return verified


def live_upload(db: Repository, upload_id: str) -> dict:
    upload = db.get_upload(upload_id)
    if upload["expires_at"] <= datetime.now(UTC).isoformat():
        raise ApiError("CONFLICT", "UPLOAD_EXPIRED", "This upload has expired; upload the file again")
    return upload


def router(state: ServiceState, current_repository: Callable[..., Repository]) -> APIRouter:
    routes = APIRouter(prefix=f"/api/{API_V2}")

    @routes.post("/uploads", response_model=UploadResponse, status_code=201)
    def create_upload(body: UploadCreate, db: Repository = Depends(current_repository)):
        limit = state.settings.max_upload_bytes
        if body.size_bytes > limit:
            raise ApiError("INVALID_INPUT", "INPUT_TOO_LARGE", f"Upload exceeds {limit} bytes", status=413)
        db.expire_uploads(state.blobs)
        upload_id = new_id("upl")
        db.add_upload(upload_id, filename=body.filename, declared_size=body.size_bytes,
                      declared_sha256=body.sha256, expires_at=_timestamp(UPLOAD_ROW_SECONDS).isoformat())
        url = state.blobs.presign(staging_key(upload_id), "PUT", UPLOAD_URL_SECONDS, body.size_bytes)
        return UploadResponse(upload_id=upload_id, url=url, expires_at=_timestamp(UPLOAD_URL_SECONDS))

    @routes.post("/uploads/{upload_id}/verify", response_model=UploadStatusResponse)
    def verify(upload_id: str, db: Repository = Depends(current_repository)):
        upload = live_upload(db, upload_id)
        if upload["status"] == "REJECTED":
            raise ApiError("CONFLICT", "UPLOAD_REJECTED", "This upload failed verification; upload the file again")
        if upload["status"] == "PENDING":
            upload = verify_upload(state, db, upload)
        return UploadStatusResponse(upload_id=upload_id, status=upload["status"], format=upload["format"],
                                    expires_at=upload["expires_at"])

    @routes.get("/analyses/{analysis_id}/artifacts/{kind}", response_model=SignedUrlResponse)
    def artifact_url(analysis_id: str, kind: str, db: Repository = Depends(current_repository)):
        # REQ-P07-S03-005: the record lookup is the access check, and it comes before any URL exists.
        record = db.get_analysis(analysis_id)
        if kind == "image":
            key = db.get_image(record.image_id).storage_key
        elif kind in ARTIFACT_KINDS:
            key = db.get_artifact(analysis_id, ARTIFACT_KINDS[kind])["storage_key"]
        else:
            raise ApiError("NOT_FOUND", "ARTIFACT_UNKNOWN", f"Unknown artifact: {kind}")
        if key is None:
            raise ApiError("NOT_FOUND", "IMAGE_NOT_STORED", f"Analysis {analysis_id} has no stored image")
        return SignedUrlResponse(url=state.blobs.presign(key, "GET", DOWNLOAD_URL_SECONDS),
                                 expires_at=_timestamp(DOWNLOAD_URL_SECONDS))

    return routes


def local_blob_router(blobs: LocalBlobStore, max_upload_bytes: int) -> APIRouter:
    """Stands in for the bucket when ``DFU_STORAGE_BACKEND=local``."""

    routes = APIRouter(prefix=f"/api/{API_V2}/blobs", include_in_schema=False)

    def _authorise(method: str, key: str, expires: int, length: int | None, signature: str) -> None:
        if not blobs.signature_valid(method, key, expires, length, signature):
            raise ApiError("NOT_FOUND", "BLOB_URL_INVALID", "This link is invalid or has expired", status=403)

    @routes.get("/{key:path}")
    def download(key: str, expires: int, signature: str):
        _authorise("GET", key, expires, None, signature)
        suffix = "." + key.rsplit(".", 1)[-1]
        return Response(blobs.get(key), media_type=MEDIA_BY_SUFFIX.get(suffix, "application/octet-stream"),
                        headers={"X-Content-Type-Options": "nosniff"})

    @routes.put("/{key:path}", status_code=200)
    async def upload(key: str, expires: int, length: int, signature: str, request: Request):
        _authorise("PUT", key, expires, length, signature)
        body = bytearray()
        async for chunk in request.stream():
            body += chunk
            if len(body) > min(length, max_upload_bytes):
                raise ApiError("INVALID_INPUT", "INPUT_TOO_LARGE", f"Upload exceeds the signed {length} bytes",
                               status=413)
        blobs.write(key, bytes(body))
        return Response(status_code=200)

    return routes


