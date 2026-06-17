"""Автоматический сбор откликов HH.ru (модуль 1 ТЗ)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.sourcing.hh_client import HHClient
from app.sourcing.scorer import score_resume
from app.storage import store

if TYPE_CHECKING:
    from app.ai.router import LLMRouter
    from app.config import Settings

logger = logging.getLogger(__name__)


async def sync_hh_responses(settings: Settings, llm: LLMRouter | None) -> dict[str, int]:
    if not settings.is_hh_configured:
        return {"vacancies": 0, "imported": 0, "skipped": 0}

    client = HHClient(settings.hh_access_token)
    vacs = await store.list_vacancies(active_only=True)
    hh_vacs = [v for v in vacs if v.hh_vacancy_id]
    imported = 0
    skipped = 0

    for vacancy in hh_vacs:
        assert vacancy.hh_vacancy_id
        try:
            items = await client.list_negotiations(vacancy.hh_vacancy_id)
        except Exception:
            logger.exception("HH sync failed for vacancy %s", vacancy.id)
            continue

        for item in items[:30]:
            resume = item.get("resume", {})
            rid = resume.get("id", "")
            if not rid:
                skipped += 1
                continue

            existing = await store.find_candidate_by_external("hh", rid)
            if existing:
                skipped += 1
                continue

            title = resume.get("title", "—")
            full = await client.get_resume(rid)
            rtext = client.resume_to_text(full) if full else title
            score, summary = None, None
            if llm and rtext:
                result = await score_resume(llm, vacancy.title, vacancy.criteria, rtext)
                score = result.get("score")
                summary = result.get("summary")

            await store.upsert_candidate(
                source="hh",
                external_id=rid,
                name=title,
                resume_text=rtext,
                vacancy_id=vacancy.id,
                match_score=score,
                match_summary=summary,
                status="new",
            )
            imported += 1

    return {"vacancies": len(hh_vacs), "imported": imported, "skipped": skipped}
