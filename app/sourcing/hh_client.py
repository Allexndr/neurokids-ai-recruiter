"""HH.ru API client — vacancies and responses (free); resume search requires paid access."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HH_API = "https://api.hh.ru"


class HHClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "recruter-support-bot/1.0",
        }

    async def search_resumes(self, text: str, area: int | None = None, per_page: int = 20) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"text": text, "per_page": per_page}
        if area:
            params["area"] = area
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(f"{HH_API}/resumes", params=params, headers=self.headers)
                if r.status_code == 403:
                    logger.warning("HH resume search requires paid employer access")
                    return []
                r.raise_for_status()
                data = r.json()
                return data.get("items", [])
        except Exception as e:
            logger.exception("HH search error: %s", e)
            return []

    async def get_resume(self, resume_id: str) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(f"{HH_API}/resumes/{resume_id}", headers=self.headers)
                if r.status_code != 200:
                    return None
                return r.json()
        except Exception:
            return None

    async def list_negotiations(self, vacancy_id: str) -> list[dict[str, Any]]:
        """Responses to employer's vacancy — free with employer token."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(
                    f"{HH_API}/negotiations/response",
                    params={"vacancy_id": vacancy_id},
                    headers=self.headers,
                )
                r.raise_for_status()
                return r.json().get("items", [])
        except Exception as e:
            logger.exception("HH negotiations error: %s", e)
            return []

    def resume_to_text(self, resume: dict[str, Any]) -> str:
        parts = []
        if resume.get("title"):
            parts.append(f"Должность: {resume['title']}")
        if resume.get("skill_set"):
            parts.append("Навыки: " + ", ".join(resume["skill_set"]))
        for exp in resume.get("experience", [])[:5]:
            desc = exp.get("position", "")
            company = exp.get("company", "")
            parts.append(f"Опыт: {desc} @ {company}")
        return "\n".join(parts)
