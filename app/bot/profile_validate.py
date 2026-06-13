"""Пошаговая валидация анкеты: имя/возраст, студент, опыт."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.bot.screening import MAX_AGE, parse_yes_no

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


def parse_name_age(text: str) -> ValidationResult:
    raw = (text or "").strip()
    if is_garbage(raw, "name_age"):
        return ValidationResult(False, "garbage")

    low = _norm(raw)
    age: int | None = None

    m = _AGE_RE.search(low) or _AGE_TRAIL_RE.search(low)
    if m:
        age = int(m.group(1))

    if age is None:
        nums = re.findall(r"\b(\d{1,2})\b", low)
        for n in nums:
            v = int(n)
            if 16 <= v <= 99:
                age = v
                break

    if age is None:
        return ValidationResult(False, "no_age")

    if age < 16:
        return ValidationResult(False, "age_young")
    if age > 55:
        return ValidationResult(False, "age_invalid")

    name_raw = raw
    if m:
        name_raw = re.sub(re.escape(m.group(0)), "", name_raw, flags=re.I)
    name_raw = re.sub(r"[,;]+", " ", name_raw)
    name_raw = re.sub(r"\d+", " ", name_raw).strip()
    name_raw = re.sub(r"\s+", " ", name_raw).strip(" ,.-")

    if not name_raw or len(name_raw) < 2:
        return ValidationResult(False, "no_name")

    if not _NAME_RE.match(name_raw) and not re.search(r"[a-zA-Zа-яёәіңғүұқөһ]", name_raw, re.I):
        return ValidationResult(False, "bad_name")

    if len(name_raw) > 40 or re.search(r"\d{3,}", name_raw):
        return ValidationResult(False, "bad_name")

    name = name_raw.split()[0].capitalize()
    if len(name_raw.split()) > 1:
        name = " ".join(w.capitalize() for w in name_raw.split()[:2])

    return ValidationResult(True, data={"name": name, "age": age})


def parse_student_answer(text: str) -> ValidationResult:
    raw = (text or "").strip()
    if is_garbage(raw, "yes_no"):
        return ValidationResult(False, "garbage")

    low = _norm(raw)
    if low in ("1", "иә", "ия", "да", "yes", "иа"):
        return ValidationResult(True, data={"is_student": True})
    if low in ("2", "жоқ", "жок", "нет", "no"):
        return ValidationResult(True, data={"is_student": False})

    yn = parse_yes_no(raw)
    if yn is None:
        if any(x in low for x in ("студент", "учусь", "универ", "сабақ", "пары")):
            if any(x in low for x in ("не ", "жоқ", "нет", "эмес")):
                return ValidationResult(True, data={"is_student": False})
            return ValidationResult(True, data={"is_student": True})
        return ValidationResult(False, "yes_no_unclear")

    return ValidationResult(True, data={"is_student": yn})


def parse_experience_answer(text: str) -> ValidationResult:
    raw = (text or "").strip()
    if is_garbage(raw, "yes_no"):
        return ValidationResult(False, "garbage")

    low = _norm(raw)
    if low in ("1", "иә", "ия", "да", "yes", "иа"):
        return ValidationResult(True, data={"has_experience": True})
    if low in ("2", "жоқ", "жок", "нет", "no"):
        return ValidationResult(True, data={"has_experience": False})

    yn = parse_yes_no(raw)
    if yn is None:
        if any(x in low for x in ("опыт", "тәжірибе", "работал", "жұмыс")):
            if any(x in low for x in ("жоқ", "нет", "не ", "без опыта")):
                return ValidationResult(True, data={"has_experience": False})
            return ValidationResult(True, data={"has_experience": True})
        return ValidationResult(False, "yes_no_unclear")

    return ValidationResult(True, data={"has_experience": yn})


def age_over_limit(age: int) -> bool:
    return age > MAX_AGE
