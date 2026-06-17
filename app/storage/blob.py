"""Vercel Blob — голосовые, резюме, кэш между serverless-вызовами."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

BLOB_API = "https://blob.vercel-storage.com"
API_VERSION = "7"


class BlobStore:
    def __init__(self, token: str, prefix: str = "hr-bot"):
        self.token = token.strip()
        self.prefix = prefix.strip("/")

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _path(self, key: str) -> str:
        key = key.lstrip("/")
        return f"{self.prefix}/{key}" if self.prefix else key

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        add_random_suffix: bool = False,
    ) -> dict[str, Any] | None:
        if not self.available:
            return None
        pathname = self._path(key)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "x-api-version": API_VERSION,
            "x-pathname": pathname,
            "x-content-type": content_type,
            "x-add-random-suffix": "1" if add_random_suffix else "0",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.put(BLOB_API, content=data, headers=headers)
                r.raise_for_status()
                return r.json()
        except Exception:
            logger.exception("Blob put failed: %s", pathname)
            return None

    async def get(self, url: str) -> bytes:
        if not url:
            return b""
        headers = {"Authorization": f"Bearer {self.token}"} if self.available else {}
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
                return r.content
        except Exception:
            logger.exception("Blob get failed: %s", url[:80])
            return b""

    async def delete(self, url: str) -> bool:
        if not self.available or not url:
            return False
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.delete(
                    BLOB_API,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "x-api-version": API_VERSION,
                    },
                    params={"url": url},
                )
                r.raise_for_status()
                return True
        except Exception:
            logger.exception("Blob delete failed")
            return False

    async def put_voice_audio(self, job_id: int, data: bytes, mime: str = "audio/ogg") -> str | None:
        meta = await self.put(f"voice/job_{job_id}.bin", data, content_type=mime, add_random_suffix=False)
        return meta.get("url") if meta else None

    async def put_resume(self, candidate_id: int, filename: str, data: bytes) -> str | None:
        safe = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)[:120] or "resume"
        meta = await self.put(
            f"resumes/candidate_{candidate_id}/{safe}",
            data,
            content_type="application/octet-stream",
            add_random_suffix=False,
        )
        return meta.get("url") if meta else None


@lru_cache
def get_blob_store() -> BlobStore:
    s = get_settings()
    return BlobStore(s.blob_read_write_token, prefix=s.blob_prefix)
