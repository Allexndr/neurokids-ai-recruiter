"""Контекстный разбор ответов (синонимы, не только «да/нет»)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.bot.screening import (
    declines_kazakh,
    detect_city,
    has_bad_schedule_pref,
    parse_yes_no,
    student_schedule_compatible,
    wants_online,
)


class StepContext(StrEnum):
    STUDENT = "student"
    EXPERIENCE = "experience"
    SCHEDULE = "schedule"
    LANGUAGE = "language"
    STUDENT_SCHEDULE = "student_schedule"
    CITY = "city"


@dataclass(frozen=True)
class SemanticResult:
    ok: bool
    value: Any = None
    error_key: str | None = None


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").lower().strip())


_POSITIVE = (
    "иә", "ия", "да", "yes", "конечно", "разумеется", "подходит", "колайлы", "қолайлы",
    "норм", "нормально", "ок", "okay", "хорошо", "отлично", "жақсы", "свободно", "свободен",
    "еркін", "еркін", "бөгде", "бегде", "владею", "билемін", "білемін", "говорю", "сөйлеймін",
    "сөйлей", "жақсы білемін", "отлично знаю", "1",
)
_NEGATIVE = (
    "жоқ", "жок", "нет", "no", "не подходит", "келмейді", "не могу", "не умею",
    "не говорю", "не знаю", "білмеймін", "билмеймін", "2",
)
def interpret_answer(text: str, ctx: StepContext, *, is_student: bool | None = None) -> SemanticResult:
    t = _norm(text)
    if not t or t in ("?", "!", "."):
        return SemanticResult(False, error_key="garbage")

    if ctx == StepContext.CITY:
        city = detect_city(text)
        if city == "almaty":
            return SemanticResult(True, value="almaty")
        if city == "other" or wants_online(text):
            return SemanticResult(True, value="other" if city == "other" else "online")
        if any(k in t for k in ("алмат", "almaty")):
            return SemanticResult(True, value="almaty")
        if len(t) >= 3 and not is_garbage_short(t):
            return SemanticResult(False, error_key="city_unclear")
        return SemanticResult(False, error_key="garbage")

    if ctx == StepContext.STUDENT_SCHEDULE:
        if student_schedule_compatible(text) or any(
            x in t for x in ("свобод", "бос", "қолай", "подходит", "могу", "буду", "все дни", "қалған")
        ):
            return SemanticResult(True, value=True)
        if any(x in t for x in ("не могу", "не подходит", "жоқ", "нет")):
            return SemanticResult(False, error_key="schedule_unclear")
        if len(t) >= 4:
            return SemanticResult(True, value=True)
        return SemanticResult(False, error_key="garbage")

    if ctx == StepContext.LANGUAGE:
        if declines_kazakh(text):
            return SemanticResult(True, value=False)
        if _is_positive(t, extra=("свобод", "еркін", "бөгде", "бегде", "казах", "қазақ")):
            return SemanticResult(True, value=True)
        if _is_negative(t):
            return SemanticResult(True, value=False)
        yn = parse_yes_no(text)
        if yn is not None:
            return SemanticResult(True, value=yn)
        return SemanticResult(False, error_key="yes_no_unclear")

    if ctx == StepContext.SCHEDULE:
        if wants_online(text) or has_bad_schedule_pref(text):
            if is_student and any(x in t for x in ("сабақ", "пары", "студент", "универ")):
                return SemanticResult(True, value="student_branch")
            return SemanticResult(True, value=False)
        if _is_positive(t, extra=("подходит", "колайлы", "норм", "удоб", "согласен")):
            return SemanticResult(True, value=True)
        if _is_negative(t):
            if is_student:
                return SemanticResult(True, value="student_branch")
            return SemanticResult(True, value=False)
        yn = parse_yes_no(text)
        if yn is True:
            return SemanticResult(True, value=True)
        if yn is False:
            if is_student:
                return SemanticResult(True, value="student_branch")
            return SemanticResult(True, value=False)
        return SemanticResult(False, error_key="yes_no_unclear")

    if ctx in (StepContext.STUDENT, StepContext.EXPERIENCE):
        # «свободен/свободно» — про график/язык, не про «вы студент?» / опыт
        yn = parse_yes_no(text)
        if yn is not None:
            return SemanticResult(True, value=yn)
        if _is_negative(t):
            return SemanticResult(True, value=False)
        if ctx == StepContext.STUDENT:
            if any(x in t for x in ("студент", "учусь", "универ", "сабақ", "пары", "колледж")):
                if any(x in t for x in ("не студент", "не учусь", "жоқ", "нет", "эмес")):
                    return SemanticResult(True, value=False)
                return SemanticResult(True, value=True)
        if ctx == StepContext.EXPERIENCE:
            if any(x in t for x in ("опыт", "тәжірибе", "работал", "жұмыс", "продав")):
                if any(x in t for x in ("без опыта", "не было", "жоқ", "нет", "не работал")):
                    return SemanticResult(True, value=False)
                return SemanticResult(True, value=True)
        if t in ("иә", "ия", "да", "yes", "1", "иа", "конечно"):
            return SemanticResult(True, value=True)
        if t in ("жоқ", "жок", "нет", "no", "2"):
            return SemanticResult(True, value=False)
        return SemanticResult(False, error_key="yes_no_unclear")

    return SemanticResult(False, error_key="garbage")


def is_garbage_short(t: str) -> bool:
    return t in ("test", "тест", "привет", "сәлем", "hello", "хз", "idk")


def _is_positive(t: str, extra: tuple[str, ...] = ()) -> bool:
    if t in _POSITIVE or any(t == x or t.startswith(x + " ") for x in _POSITIVE):
        return True
    return any(x in t for x in extra)


def _is_negative(t: str) -> bool:
    if t in _NEGATIVE:
        return True
    if any(x in t for x in _NEGATIVE):
        return True
    if t.startswith("не ") and "свобод" not in t:
        return True
    return False
