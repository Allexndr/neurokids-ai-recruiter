"""Configurable screening against active vacancy criteria."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.bot.screening import RejectReason, detect_city, wants_online


@dataclass
class VacancyCriteria:
    max_age: int = 65
    min_age: int = 16
    cities: list[str] | None = None
    require_kazakh: bool = False
    allow_remote: bool = True
    schedule_6_1: bool = False

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> VacancyCriteria:
        return cls(
            max_age=int(data.get("max_age", 65)),
            min_age=int(data.get("min_age", 16)),
            cities=data.get("cities"),
            require_kazakh=bool(data.get("require_kazakh", False)),
            allow_remote=bool(data.get("allow_remote", True)),
            schedule_6_1=bool(data.get("schedule_6_1", False)),
        )


def screen_with_criteria(profile: dict[str, Any], criteria: VacancyCriteria, lang: str = "ru") -> RejectReason | None:
    from app.bot import content_ru as RU

    age = profile.get("age")
    if age is not None:
        try:
            age_n = int(age)
            if age_n > criteria.max_age:
                return RejectReason("age", RU.REJECT_AGE)
            if age_n < criteria.min_age:
                return RejectReason("age", RU.ERR_AGE_YOUNG)
        except (TypeError, ValueError):
            pass

    if not criteria.allow_remote and profile.get("wants_online"):
        return RejectReason("online", RU.REJECT_ONLINE)

    if criteria.cities:
        city = (profile.get("city") or "").lower()
        allowed = [c.lower() for c in criteria.cities]
        if city and city not in allowed and not any(a in city for a in allowed):
            if detect_city(city) == "other" or city == "other":
                return RejectReason("city", RU.REJECT_CITY)

    if criteria.require_kazakh and profile.get("language_ok") is False:
        return RejectReason("language", RU.REJECT_LANGUAGE)

    if profile.get("declines_kazakh"):
        return RejectReason("language", RU.REJECT_LANGUAGE)

    return None
