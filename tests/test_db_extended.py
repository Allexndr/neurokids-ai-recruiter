import pytest

from app.storage.db import Store


@pytest.fixture
async def mem_store(tmp_path):
    s = Store(str(tmp_path / "test.sqlite3"))
    await s.init()
    return s


@pytest.mark.asyncio
async def test_vacancy_and_candidate(mem_store):
    vid = await mem_store.create_vacancy("Dev", {"skills": ["python"]})
    assert vid > 0
    cid = await mem_store.upsert_candidate(
        source="telegram", chat_id="123", name="Test", resume_text="python dev", vacancy_id=vid, match_score=80
    )
    assert cid > 0
    cands = await mem_store.list_candidates(vacancy_id=vid)
    assert len(cands) == 1
    assert cands[0].match_score == 80


@pytest.mark.asyncio
async def test_interview_analysis(mem_store):
    cid = await mem_store.upsert_candidate(source="file", name="A", resume_text="text")
    iid = await mem_store.create_interview(cid, 1700000000)
    aid = await mem_store.save_interview_analysis(cid, "transcript", "summary", {"strengths": ["x"]}, iid)
    assert aid > 0
