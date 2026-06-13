from __future__ import annotations

import csv
import io
import json
import logging
import re
from typing import Any

from app.ai.prompts_hr import SCORE_SYSTEM, SCORE_USER
from app.ai.router import LLMRouter

logger = logging.getLogger(__name__)


async def score_resume(
    llm: LLMRouter,
    vacancy_title: str,
    criteria: dict[str, Any],
    resume_text: str,
) -> dict[str, Any]:
    if not resume_text.strip():
        return {"score": 0, "summary": "Пустое резюме", "matched_skills": [], "gaps": ["нет данных"]}

    user = SCORE_USER.format(
        title=vacancy_title,
        criteria=json.dumps(criteria, ensure_ascii=False),
        resume=resume_text[:12000],
    )
    content, err = await llm.chat(
        [{"role": "system", "content": SCORE_SYSTEM}, {"role": "user", "content": user}],
        max_tokens=600,
    )
    if not content:
        logger.error("Score failed: %s", err)
        return _heuristic_score(criteria, resume_text)

    parsed = _parse_json(content)
    if parsed:
        parsed["score"] = max(0, min(100, int(parsed.get("score", 0))))
        return parsed
    return _heuristic_score(criteria, resume_text)


def _heuristic_score(criteria: dict[str, Any], resume_text: str) -> dict[str, Any]:
    low = resume_text.lower()
    skills = criteria.get("skills") or []
    matched = [s for s in skills if str(s).lower() in low]
    score = int(40 + 60 * len(matched) / max(len(skills), 1)) if skills else 50
    return {
        "score": min(100, score),
        "summary": "Эвристическая оценка (LLM недоступен)",
        "matched_skills": matched,
        "gaps": [s for s in skills if s not in matched],
    }


def _parse_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                return None
    return None


def parse_csv_candidates(data: bytes) -> list[dict[str, str]]:
    text = data.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, str]] = []
    for row in reader:
        normalized = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        rows.append(normalized)
    return rows
