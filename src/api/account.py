"""P07-S04 account routes: a user can take their data away or remove it."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends

from src.api.schemas import API_V2, DeleteResponse, ExportResponse
from src.api.service import ServiceState
from src.storage.repository import Repository

EXPORT_URL_SECONDS = 3600  # long enough to download a whole account


def router(state: ServiceState, current_repository: Callable[..., Repository]) -> APIRouter:
    routes = APIRouter(prefix=f"/api/{API_V2}/account")

    def _with_url(row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("storage_key")
        url = state.blobs.presign(key, "GET", EXPORT_URL_SECONDS) if key else None
        return {**row, "url": url}

    @routes.get("/export", response_model=ExportResponse)
    def export(db: Repository = Depends(current_repository)):
        data = db.export()
        data["images"] = [_with_url(row) for row in data["images"]]
        data["artifacts"] = [_with_url(row) for row in data["artifacts"]]
        return ExportResponse(api_version=API_V2, url_expires_in_seconds=EXPORT_URL_SECONDS, **data)

    @routes.delete("", response_model=DeleteResponse)
    def delete_account(db: Repository = Depends(current_repository)):
        return DeleteResponse(api_version=API_V2, deleted=db.delete_account(state.blobs))

    return routes
