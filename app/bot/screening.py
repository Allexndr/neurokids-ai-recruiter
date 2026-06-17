"""Вспомогательные функции парсинга ответов (без воронки Ataman)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RejectReason:
    code: str
    message: str


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").lower().strip())


def parse_yes_no(text: str) -> bool | None:
    t = _norm(text)
    if t in ("иә", "ия", "да", "yes", "ok", "ок", "1", "иа", "конечно", "разумеется"):
        return True
    if t in ("жоқ", "жок", "нет", "no", "2"):
        return False
    if any(x in t for x in ("подходит", "колайлы", "норм", "согласен", "удобно", "активно", "ищу")):
        return True
    if re.search(r"\b(нет|no|жоқ|жок)\b", t):
        return False
    return None


def screen_profile(profile: dict[str, Any], lang: str) -> RejectReason | None:
    _ = profile, lang
    return None


def screen_schedule_answer(text: str, lang: str, is_student: bool | None) -> RejectReason | str | None:
    _ = text, lang, is_student
    return None


def screen_language_answer(text: str, lang: str) -> RejectReason | bool | None:
    _ = text, lang
    return None


def detect_city(text: str) -> str | None:
    t = _norm(text)
    if "алмат" in t or "almaty" in t:
        return "almaty"
    return None


def wants_online(text: str) -> bool:
    t = _norm(text)
    return any(k in t for k in ("онлайн", "online", "удален", "удалён", "remote"))


def declines_kazakh(text: str) -> bool:
    _ = text
    return False


def has_bad_schedule_pref(text: str) -> bool:
    _ = text
    return False


def is_flexible_student_case(text: str, is_student: bool | None) -> bool:
    _ = text, is_student
    return False


def student_schedule_compatible(text: str) -> bool:
    _ = text
    return True


def regex_parse_profile(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    out: dict[str, Any] = {}
    if len(t) >= 2:
        out["name"] = t.split()[0].capitalize()
    yn = parse_yes_no(t)
    if yn is not None:
        out["job_search_active"] = yn
    if len(t) >= 15:
        out["experience_summary"] = t[:500]
    return out
