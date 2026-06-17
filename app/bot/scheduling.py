from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.calendar.google_calendar import GoogleCalendarClient

WORK_START_H = 10
WORK_END_H = 20
TODAY_CUTOFF_H = 19
SLOT_HOURS = (11, 14)
MAX_WORKING_DAYS = 3


@dataclass(frozen=True)
class InterviewSlot:
    slot_id: str
    label_kk: str
    label_ru: str
    starts_at: datetime


def _tz(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("Asia/Almaty")


def _is_working_day(d: datetime) -> bool:
    return d.weekday() not in (6, 0)  # вс, пн — выходные


def _slot_labels(dt: datetime) -> tuple[str, str]:
    months_kk = (
        "қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым",
        "шілде", "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан",
    )
    m = months_kk[dt.month - 1]
    kk = f"{dt.day} {m}, {dt.strftime('%H:%M')}"
    ru = dt.strftime("%d.%m.%Y %H:%M")
    return kk, ru


def available_slots(now: datetime | None = None, tz_name: str = "Asia/Almaty") -> list[InterviewSlot]:
    tz = _tz(tz_name)
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    slots: list[InterviewSlot] = []
    day = now.date()
    working_days_found = 0

    while working_days_found < MAX_WORKING_DAYS:
        cur = datetime.combine(day, datetime.min.time(), tzinfo=tz)
        if _is_working_day(cur):
            working_days_found += 1
            is_today = day == now.date()
            for hour in SLOT_HOURS:
                start = cur.replace(hour=hour, minute=0)
                if start <= now:
                    continue
                if is_today and hour >= TODAY_CUTOFF_H:
                    continue
                if hour < WORK_START_H or hour >= WORK_END_H:
                    continue
                sid = start.strftime("%Y%m%d%H%M")
                lk, lr = _slot_labels(start)
                slots.append(InterviewSlot(sid, lk, lr, start))

            if is_today and now.hour < TODAY_CUTOFF_H and now.hour >= WORK_START_H:
                start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                if start.hour < TODAY_CUTOFF_H:
                    sid = f"today{TODAY_CUTOFF_H}00"
                    lk = f"Бүгін {TODAY_CUTOFF_H}:00-ге дейін"
                    lr = f"Сегодня до {TODAY_CUTOFF_H}:00"
                    slots.insert(
                        0,
                        InterviewSlot(sid, lk, lr, start.replace(hour=TODAY_CUTOFF_H, minute=0)),
                    )

        day += timedelta(days=1)
        if (day - now.date()).days > 14:
            break

    seen: set[str] = set()
    unique: list[InterviewSlot] = []
    for s in slots:
        if s.slot_id not in seen:
            seen.add(s.slot_id)
            unique.append(s)
    return unique[:6]


def bookable_slots(
    tz_name: str = "Asia/Almaty",
    gcal: GoogleCalendarClient | None = None,
    now: datetime | None = None,
) -> list[InterviewSlot]:
    """Слоты с учётом занятости HR-календаря (модуль 3 ТЗ)."""
    slots = available_slots(now=now, tz_name=tz_name)
    if gcal and gcal.available:
        tz = _tz(tz_name)
        ref = now or datetime.now(tz)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=tz)
        else:
            ref = ref.astimezone(tz)
        busy = gcal.get_busy_slots(ref, ref + timedelta(days=14))
        slots = gcal.filter_available_slots(slots, busy)
    return slots


def slot_by_id(
    slot_id: str,
    now: datetime | None = None,
    tz_name: str = "Asia/Almaty",
    gcal: GoogleCalendarClient | None = None,
) -> InterviewSlot | None:
    for s in bookable_slots(tz_name=tz_name, gcal=gcal, now=now):
        if s.slot_id == slot_id:
            return s
    return None


def format_slot_label(slot: InterviewSlot, lang: str) -> str:
    return slot.label_kk if lang == "kk" else slot.label_ru
