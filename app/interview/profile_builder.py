from __future__ import annotations

import json
import re
from typing import Any

from app.ai.prompts_hr import PROFILE_SYSTEM
from app.ai.router import LLMRouter


async def build_interview_profile(
    llm: LLMRouter,
    transcript: str,
    candidate_name: str = "",
    vacancy_title: str = "",
) -> dict[str, Any]:
    if not transcript.strip():
        return {"summary": "Пустая транскрипция", "key_topics": []}

    user = f"Кандидат: {candidate_name}\nВакансия: {vacancy_title}\n\nТранскрипция:\n{transcript[:15000]}"
    content, _ = await llm.chat(
        [{"role": "system", "content": PROFILE_SYSTEM}, {"role": "user", "content": user}],
        max_tokens=1200,
    )
    if not content:
        return {"summary": transcript[:500], "key_topics": [], "recommendations": ["Повторить анализ при доступном LLM"]}

    parsed = _parse_json(content)
    return parsed or {"summary": content[:800], "key_topics": []}


def format_profile_card(profile: dict[str, Any], candidate_name: str) -> str:
    lines = [f"<b>Карточка кандидата: {candidate_name}</b>", ""]
    if profile.get("summary"):
        lines.append(f"<b>Выжимка:</b> {profile['summary']}")
    if profile.get("motivation"):
        lines.append(f"<b>Мотивация:</b> {profile['motivation']}")
    for label, key in (
        ("Сильные стороны", "strengths"),
        ("Слабые стороны", "weaknesses"),
        ("Интересы", "interests"),
        ("Рекомендации HR", "recommendations"),
        ("Уточняющие вопросы", "follow_up_questions"),
    ):
        val = profile.get(key)
        if val:
            if isinstance(val, list):
                lines.append(f"<b>{label}:</b> " + "; ".join(str(v) for v in val))
            else:
                lines.append(f"<b>{label}:</b> {val}")
    return "\n".join(lines)


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
