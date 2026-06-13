from datetime import datetime
from zoneinfo import ZoneInfo

from app.bot.scheduling import available_slots


def test_no_sunday_monday_slots():
    tz = ZoneInfo("Asia/Almaty")
    # 2026-06-07 is Sunday
    now = datetime(2026, 6, 7, 12, 0, tzinfo=tz)
    slots = available_slots(now=now, tz_name="Asia/Almaty")
    for s in slots:
        assert s.starts_at.weekday() not in (6, 0)


def test_slots_limited():
    tz = ZoneInfo("Asia/Almaty")
    now = datetime(2026, 6, 4, 10, 0, tzinfo=tz)  # Thursday
    slots = available_slots(now=now, tz_name="Asia/Almaty")
    assert len(slots) <= 6
    assert len(slots) >= 1
