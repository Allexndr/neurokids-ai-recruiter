import pytest

from app.bot.scheduling import available_slots, bookable_slots


def test_bookable_slots_without_calendar():
    slots = bookable_slots(tz_name="Asia/Almaty", gcal=None)
    base = available_slots(tz_name="Asia/Almaty")
    assert len(slots) == len(base)
    assert slots[0].slot_id == base[0].slot_id


@pytest.mark.asyncio
async def test_add_hr_comment_sqlite(tmp_path):
    from app.storage.db import Store

    store = Store(str(tmp_path / "t.sqlite3"))
    await store.init()
    vid = await store.create_vacancy("Test", {"skills": []})
    cid = await store.upsert_candidate(source="file", name="A", vacancy_id=vid)
    ok = await store.add_hr_comment(cid, "Сильный кандидат")
    assert ok
    c = await store.get_candidate(cid)
    assert c.profile["hr_comments"][0]["text"] == "Сильный кандидат"


@pytest.mark.asyncio
async def test_find_candidate_by_external(tmp_path):
    from app.storage.db import Store

    store = Store(str(tmp_path / "t2.sqlite3"))
    await store.init()
    await store.upsert_candidate(source="hh", external_id="abc123", name="X")
    found = await store.find_candidate_by_external("hh", "abc123")
    assert found and found.name == "X"
    assert await store.find_candidate_by_external("hh", "missing") is None
