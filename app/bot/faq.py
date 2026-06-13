from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

from app.bot import content_kk as KK
from app.bot import content_ru as RU
from app.ai.prompts import FAQ_SYSTEM

if TYPE_CHECKING:
    from app.together_client import TogetherClient

_CACHE: OrderedDict[str, str] = OrderedDict()
_CACHE_LIMIT = 150

_KB_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_ataman.md"


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").lower().strip())


def _c(lang: str):
    return KK if lang == "kk" else RU


def load_knowledge() -> str:
    if _KB_PATH.is_file():
        return _KB_PATH.read_text(encoding="utf-8")
    return ""


_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("стаж", "интерн", "стажиров", "тағылым"), "internship"),
    (("опыт", "тәжірибе", "тажирибе", "маңызды ма"), "experience"),
    (("график", "режим", "уақыт", "10:00", "6/1"), "schedule"),
    (("не сат", "не прода", "өнім", "продукт", "товар"), "product"),
    (("оклад", "айлық", "месяц"), "salary_detail"),
    (("%", "процент", "пайыз", "қанша %"), "percent"),
    (("зп", "зарплат", "табам", "табы", "ақша", "жалақы", "750"), "salary"),
    (("жұмыс", "работа", "сетев", "mlm", "отдел"), "job"),
    (("компания", "нарық", "клиент", "2 жыл"), "company"),
    (("мекен", "адрес", "офис", "алтын заман", "2gis"), "address"),
]


def keyword_faq(text: str, lang: str) -> str | None:
    t = _norm(text)
    for keys, key in _PATTERNS:
        if any(k in t for k in keys):
            c = _c(lang)
            return {
                "internship": c.FAQ_INTERNSHIP,
                "experience": c.FAQ_EXPERIENCE,
                "schedule": c.FAQ_SCHEDULE,
                "product": c.FAQ_PRODUCT,
                "salary": c.FAQ_SALARY,
                "salary_detail": c.FAQ_SALARY_DETAIL,
                "percent": c.FAQ_PERCENT,
                "job": c.FAQ_JOB,
                "company": c.FAQ_COMPANY,
                "address": (
                    "📍 БЦ Алтын заман, 4 этаж, 401Б\n"
                    "https://2gis.kz/almaty/geo/9429940001536524/76.933636,43.251586"
                ),
            }.get(key)
    return None


def _cache_get(key: str) -> str | None:
    v = _CACHE.get(key)
    if v is not None:
        _CACHE.move_to_end(key)
    return v


def _cache_put(key: str, value: str) -> None:
    _CACHE[key] = value
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_LIMIT:
        _CACHE.popitem(last=False)


async def answer_faq(
    text: str,
    lang: str,
    together: TogetherClient | None,
) -> str | None:
    hit = keyword_faq(text, lang)
    if hit:
        return hit

    if not together:
        return None

    cache_key = f"{lang}||{_norm(text)}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    kb = load_knowledge()
    messages = [
        {"role": "system", "content": f"{FAQ_SYSTEM}\n\nБаза:\n{kb}"},
        {"role": "user", "content": text},
    ]
    answer, _ = await together.chat(messages, temperature=0.2, max_tokens=200)
    if answer:
        _cache_put(cache_key, answer)
    return answer
