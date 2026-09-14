"""Pluggable upload storage: local disk or Supabase Storage.

Cloud containers have ephemeral filesystems, so production uploads go to
Supabase Storage (already part of the stack — a private bucket, service-role
key) while local development keeps writing to disk unchanged. The reference
string returned by ``save_upload`` is what gets persisted in ``file_path`` /
``image_path`` columns: either a filesystem path or a Storage object key.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)

#: Storage bucket for uploads. Private: downloads must go through the API so
#: auth is enforced (the service-role key never reaches the browser).
UPLOAD_BUCKET = "lease-uploads"


class UploadStorage:
    """Persists one upload and returns the reference string to store."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None  # Lazily built Supabase client.

    @property
    def uses_object_storage(self) -> bool:
        """Whether uploads go to Supabase Storage rather than local disk."""
        return bool(
            self.settings.supabase_storage_enabled
            and self.settings.supabase_url
            and self.settings.supabase_service_role_key
        )

    def save_upload(self, raw_bytes: bytes, file_name: str, content_type: str | None) -> str:
        """Persist one upload, returning the reference string to store.

        Raises on failure so callers can reject the request instead of holding
        a database row that points at nothing.
        """
        stored_name = f"{uuid.uuid4()}_{file_name}"
        if self.uses_object_storage:
            return self._save_to_supabase(raw_bytes, stored_name, content_type)
        return self._save_to_disk(raw_bytes, stored_name)

    def open_download(self, reference: str) -> tuple[bytes, str]:
        """Return (bytes, content_type) for a previously stored reference."""
        if self.uses_object_storage and not reference.startswith("/"):
            return self._open_from_supabase(reference)
        return self._open_from_disk(reference)

    # --- Backends ---------------------------------------------------------
    def _save_to_disk(self, raw_bytes: bytes, stored_name: str) -> str:
        storage_dir = Path(self.settings.document_storage_path)
        storage_dir.mkdir(parents=True, exist_ok=True)
        stored_path = storage_dir / stored_name
        stored_path.write_bytes(raw_bytes)
        return str(stored_path)

    def _open_from_disk(self, reference: str) -> tuple[bytes, str]:
        path = Path(reference)
        # Local dev served an upload path; keep the content type honest enough
        # for browsers to render images without sniffing.
        media_type = _guess_media_type(path.name)
        return path.read_bytes(), media_type

    def _get_client(self):
        if self._client is None:
            from supabase import create_client

            self._client = create_client(
                self.settings.supabase_url or "",
                self.settings.supabase_service_role_key or "",
            )
        return self._client

    def _save_to_supabase(
        self, raw_bytes: bytes, stored_name: str, content_type: str | None
    ) -> str:
        bucket = self._get_client().storage.from_(UPLOAD_BUCKET)
        # Content type is what makes signed-URL downloads render instead of
        # forcing a generic octet-stream download.
        options = {"content-type": content_type or "application/octet-stream"}
        bucket.upload(stored_name, raw_bytes, options)
        return stored_name

    def _open_from_supabase(self, reference: str) -> tuple[bytes, str]:
        bucket = self._get_client().storage.from_(UPLOAD_BUCKET)
        response = bucket.download(reference)
        return response, _guess_media_type(reference)


def _guess_media_type(name: str) -> str:
    """Minimal extension mapping; Supabase already stored the real type on upload."""
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
        "pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")
