"""Пошаговая валидация анкеты кандидата (TZ: модуль 2)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.bot.screening import parse_yes_no

_NAME_RE = re.compile(
    r"^[\s\d]*([a-zA-Zа-яёА-ЯЁәіңғүұқөһӘІҢҒҮҰҚӨҺ][a-zA-Zа-яёәіңғүұқөһӘІҢҒҮҰҚӨҺ\s\-']{1,35})$",
    re.UNICODE,
)
_AGE_RE = re.compile(r"\b(\d{1,2})\s*(?:лет|жас|года|г\.|age|те)?\b", re.I)
_AGE_TRAIL_RE = re.compile(r"(\d{1,2})\s*[-–]?\s*(?:те|лет|жас)?\s*$", re.I)

_JUNK_EXACT = frozenset(
    {
        "test", "тест", "asd", "qwe", "qwerty", "hello", "привет", "салем", "сәлем",
        "ok", "ок", "?", "!", ".", "хз", "не знаю", "билмеймін", "idk", "лол", "lol",
        "123", "111", "000", "может быть", "мүмкін", "билмеймін",
    }
)
_JUNK_SUBSTR = ("http", "www.", "@", "telegram", "whatsapp", "подпис", "реклам")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error_key: str | None = None
    data: dict[str, Any] | None = None


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def is_garbage(text: str, step: str) -> bool:
    t = _norm(text)
    if len(t) < 2 and not (step == "yes_no" and t in ("1", "2")):
        return True
    if t in _JUNK_EXACT:
        return True
    if any(s in t for s in _JUNK_SUBSTR):
        return True
    if step != "yes_no" and re.fullmatch(r"[\d\W_]+", t):
        return True
    if step == "yes_no" and re.fullmatch(r"[\d\W_]+", t) and t not in ("1", "2"):
        return True
    if step == "yes_no" and len(t) > 40:
        return True
    if step == "name_age" and len(t) > 80:
        return True
    profanity = ("хуй", "пизд", "бля", "сука", "fuck", "shit")
    if any(p in t for p in profanity):
        return True
    return False


def parse_name(text: str) -> ValidationResult:
    raw = (text or "").strip()
    if is_garbage(raw, "name_age"):
        return ValidationResult(False, "garbage")
    name_raw = re.sub(r"[,;]+", " ", raw)
    name_raw = re.sub(r"\d+", " ", name_raw).strip()
    name_raw = re.sub(r"\s+", " ", name_raw).strip(" ,.-")
    if not name_raw or len(name_raw) < 2:
        return ValidationResult(False, "no_name")
    if not _NAME_RE.match(name_raw) and not re.search(r"[a-zA-Zа-яёәіңғүұқөһ]", name_raw, re.I):
        return ValidationResult(False, "bad_name")
    if len(name_raw) > 40:
        return ValidationResult(False, "bad_name")
    parts = name_raw.split()
    name = " ".join(w.capitalize() for w in parts[:2])
    return ValidationResult(True, data={"name": name})


def parse_name_age(text: str) -> ValidationResult:
    """Совместимость: только имя."""
    return parse_name(text)


def parse_job_search_answer(text: str) -> ValidationResult:
    raw = (text or "").strip()
    if is_garbage(raw, "yes_no"):
        return ValidationResult(False, "garbage")
    yn = parse_yes_no(raw)
    if yn is None:
        return ValidationResult(False, "yes_no_unclear")
    return ValidationResult(True, data={"job_search_active": yn})


def parse_experience_text(text: str) -> ValidationResult:
    raw = (text or "").strip()
    if is_garbage(raw, "name_age"):
        return ValidationResult(False, "garbage")
    if len(raw) < 8:
        return ValidationResult(False, "experience_short")
    return ValidationResult(True, data={"experience_summary": raw[:2000]})


def parse_student_answer(text: str) -> ValidationResult:
    r = parse_job_search_answer(text)
    if not r.ok:
        return r
    return ValidationResult(True, data={"is_student": r.data.get("job_search_active")})


def parse_experience_answer(text: str) -> ValidationResult:
    yn = parse_yes_no(text)
    if yn is not None:
        return ValidationResult(True, data={"has_experience": yn})
    return parse_experience_text(text)


def age_over_limit(age: int) -> bool:
    _ = age
    return False
