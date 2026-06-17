from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    CHOOSE_LANG = "choose_lang"
    GREETING = "greeting"
    COLLECT_NAME_AGE = "collect_name_age"
    COLLECT_STUDENT = "collect_student"
    COLLECT_EXPERIENCE = "collect_experience"
    COLLECT_PROFILE = "collect_profile"
    COLLECT_CITY = "collect_city"
    COLLECT_SCHEDULE = "collect_schedule"
    STUDENT_SCHEDULE = "student_schedule"
    COLLECT_LANGUAGE = "collect_language"
    SCREEN = "screen"
    WELCOME_QUALIFIED = "welcome_qualified"
    QA = "qa"
    SCHEDULE_INTERVIEW = "schedule_interview"
    CONFIRM = "confirm"
    REJECTED = "rejected"
    CLOSED = "closed"
    HANDOFF_HR = "handoff_hr"
