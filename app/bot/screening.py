from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.bot import content_kk as KK
from app.bot import content_ru as RU

MAX_AGE = 30
ALMATY_KEYS = ("алматы", "almaty", "алмата")
OTHER_CITY_KEYS = (
    "астана", "астаны", "шымкент", "актау", "атырау", "караганда",
    "павлодар", "тараз", "усть", "семей", "костанай", "актуобе",
    "кызылорда", "уральск", "петропавл", "тараз", "туркестан",
)
ONLINE_KEYS = ("онлайн", "online", "удален", "удалён", "удаленк", "remote", "из дома")
BAD_SCHEDULE_KEYS = ("2/2", "3/3", "5/2", "2-2", "3-3", "5-2", "гибк", "гибкий", "гибкии")
FLEX_SCHEDULE_KEYS = ("гибк", "гибкий", "сабақ", "пары", "универ", "студент")
NO_KAZAKH_KEYS = (
    "не знаю казах", "не говорю по-казах", "казахский не",
    "қазақша білмей", "білмеймін", "не владею казах",
)


@dataclass(frozen=True)
class RejectReason:
    code: str
    message: str


def _c(lang: str):
    return KK if lang == "kk" else RU


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").lower().strip())


def parse_yes_no(text: str) -> bool | None:
    t = _norm(text)
    if t in ("иә", "ия", "да", "yes", "ok", "ок", "1", "иа", "конечно", "разумеется"):
        return True
    if t in ("жоқ", "жок", "нет", "no", "2"):
        return False
    if any(x in t for x in ("подходит", "колайлы", "норм", "согласен", "удобно")):
        return True
    if re.search(r"\b(нет|no|жоқ|жок)\b", t):
        return False
    if re.search(r"\bне\s+(знаю|говорю|владею|білем|билем)\b", t):
        return False
    return None


def detect_city(text: str) -> str | None:
    t = _norm(text)
    if any(k in t for k in ALMATY_KEYS):
        return "almaty"
    for k in OTHER_CITY_KEYS:
        if k in t:
            return "other"
    return None


def wants_online(text: str) -> bool:
    t = _norm(text)
    return any(k in t for k in ONLINE_KEYS)


def declines_kazakh(text: str) -> bool:
    t = _norm(text)
    return any(k in t for k in NO_KAZAKH_KEYS)


def has_bad_schedule_pref(text: str) -> bool:
    t = _norm(text)
    return any(k in t for k in BAD_SCHEDULE_KEYS)


def is_flexible_student_case(text: str, is_student: bool | None) -> bool:
    t = _norm(text)
    if is_student:
        return True
    return any(k in t for k in FLEX_SCHEDULE_KEYS) and "6/1" not in t and "6-1" not in t


def student_schedule_compatible(text: str) -> bool:
    """Пн выходной у компании — если только пн занят, остальное ок."""
    t = _norm(text)
    if "понедельник" in t or "дүйсенбі" in t or "дуйсенби" in t:
        if any(x in t for x in ("сабақ", "пары", "14:00", "14-00", "универ")):
            return True
    if "четверг" in t or "бейсенбі" in t:
        return True
    if "бос" in t or "свобод" in t or "қалған" in t or "полностью" in t:
        return True
    if len(t) >= 5 and not has_bad_schedule_pref(text):
        return True
    return False


def screen_profile(profile: dict[str, Any], lang: str) -> RejectReason | None:
    age = profile.get("age")
    if age is not None:
        try:
            age_n = int(age)
            if age_n > MAX_AGE:
                return RejectReason("age", _c(lang).REJECT_AGE)
        except (TypeError, ValueError):
            pass

    city = (profile.get("city") or "").lower()
    if profile.get("wants_online"):
        return RejectReason("online", _c(lang).REJECT_ONLINE)
    if city == "other" or (city and city not in ("almaty", "алматы")):
        if "алмат" not in city:
            return RejectReason("city", _c(lang).REJECT_CITY)

    if profile.get("declines_kazakh") or profile.get("language_ok") is False:
        return RejectReason("language", _c(lang).REJECT_LANGUAGE)

    return None


def screen_schedule_answer(text: str, lang: str, is_student: bool | None) -> RejectReason | str | None:
    """
    Returns RejectReason, 'student_branch', 'ok', or None (unclear).
    """
    yn = parse_yes_no(text)
    if yn is True:
        return "ok"
    if yn is False:
        if is_flexible_student_case(text, is_student):
            return "student_branch"
        return RejectReason("schedule", _c(lang).REJECT_SCHEDULE)

    if wants_online(text):
        return RejectReason("online", _c(lang).REJECT_ONLINE)

    if has_bad_schedule_pref(text):
        if is_flexible_student_case(text, is_student):
            return "student_branch"
        return RejectReason("schedule", _c(lang).REJECT_SCHEDULE)

    if is_flexible_student_case(text, is_student):
        return "student_branch"

    return None


def screen_language_answer(text: str, lang: str) -> RejectReason | bool | None:
    from app.bot.semantic import StepContext, interpret_answer

    r = interpret_answer(text, StepContext.LANGUAGE)
    if r.ok:
        if r.value is False:
            return RejectReason("language", _c(lang).REJECT_LANGUAGE)
        return True
    if declines_kazakh(text):
        return RejectReason("language", _c(lang).REJECT_LANGUAGE)
    return None


def regex_parse_profile(text: str) -> dict[str, Any]:
    """Lightweight parse without LLM."""
    t = text.strip()
    low = _norm(t)
    out: dict[str, Any] = {}

    age_m = re.search(r"(\d{2})\s*[-–]?\s*(те|лет|жас|года|г\.|age)?", low)
    if age_m:
        out["age"] = int(age_m.group(1))

    parts = re.split(r"[,;\n]+", t)
    if parts:
        name_part = parts[0].strip()
        name_part = re.sub(r"\d+.*", "", name_part).strip()
        if name_part and len(name_part) < 40:
            out["name"] = name_part.split()[0].capitalize() if name_part else None

    if re.search(r"\b(студент|student|студентс)\b", low):
        out["is_student"] = True
    if "жоқ" in low or "нет" in low:
        if "студент" in low or len(parts) >= 3:
            pass
    for i, p in enumerate(parts):
        pl = _norm(p)
        if pl in ("жоқ", "жок", "нет", "no"):
            if i == 1:
                out["is_student"] = False
            elif i == 2:
                out["has_experience"] = False
        if pl in ("иә", "да", "yes"):
            if i == 1:
                out["is_student"] = True
            elif i == 2:
                out["has_experience"] = True

    city = detect_city(text)
    if city:
        out["city"] = city
    if wants_online(text):
        out["wants_online"] = True
    if declines_kazakh(text):
        out["declines_kazakh"] = True

    return out
