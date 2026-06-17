import time

import pytest

from app.interview.audio_chunker import estimate_total_chunks
from app.storage.db import Store


def test_estimate_total_chunks():
    assert estimate_total_chunks(40, 300) == 1
    assert estimate_total_chunks(300, 300) == 1
    assert estimate_total_chunks(301, 300) == 2
    assert estimate_total_chunks(2400, 300) == 8


@pytest.mark.asyncio
async def test_voice_job_lifecycle(tmp_path):
    db = Store(str(tmp_path / "voice.sqlite3"))
    await db.init()

    job_id = await db.create_voice_job(
        chat_id="123",
        file_id="abc",
        duration_sec=600,
        file_size=1000,
        total_chunks=2,
        candidate_id=7,
        contact_name="Test",
    )
    job = await db.get_voice_job(job_id)
    assert job is not None
    assert job.status == "pending"
    assert job.chunk_index == 0
    assert job.total_chunks == 2

    await db.mark_voice_job_processing(job_id)
    job = await db.append_voice_chunk(job_id, "первая часть")
    assert job is not None
    assert job.chunk_index == 1
    assert job.parts == ["первая часть"]

    job = await db.append_voice_chunk(job_id, "вторая часть")
    assert job.chunk_index == 2
    assert job.full_transcript() == "первая часть\n\nвторая часть"

    await db.complete_voice_job(job_id)
    job = await db.get_voice_job(job_id)
    assert job.status == "done"

    await db.fail_voice_job(job_id, "ignored")
    job = await db.get_voice_job(job_id)
    assert job.status == "failed"


@pytest.mark.asyncio
async def test_list_stale_voice_jobs(tmp_path):
    db = Store(str(tmp_path / "stale.sqlite3"))
    await db.init()
    job_id = await db.create_voice_job("1", "f", 60, 100, 1)

    import aiosqlite

    async with aiosqlite.connect(db.path) as conn:
        await conn.execute(
            "UPDATE voice_jobs SET updated_at = ? WHERE id = ?",
            (int(time.time()) - 120, job_id),
        )
        await conn.commit()

    stale = await db.list_stale_voice_jobs(limit=5, stale_sec=60)
    ids = [j.id for j in stale]
    assert job_id in ids
