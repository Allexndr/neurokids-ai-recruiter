"""Background voice transcription — one chunk per serverless invocation."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

from app.config import Settings
from app.bot.keyboards import confirm_keyboard
from app.bot.outbound import update_panel, use_telegram_panel
from app.interview.audio_chunker import estimate_total_chunks, extract_chunk_bytes
from app.interview.profile_builder import build_interview_profile, format_profile_card
from app.interview.transcribe import transcribe_audio
from app.storage import store
from app.storage.blob import get_blob_store
from app.hr_notify import notify_hr_text
from app.telegram_api import TelegramClient

logger = logging.getLogger(__name__)


async def _panel_notify(
    tg: TelegramClient,
    chat_id: str,
    text: str,
    reply_markup: dict | None = None,
) -> None:
    session = await store.get_session(chat_id)
    if use_telegram_panel(session):
        await update_panel(tg, session, chat_id, text, reply_markup)
        await store.save_session(session)
    else:
        await tg.send_message(chat_id, text, reply_markup=reply_markup)


def _format_duration(sec: int) -> str:
    sec = max(0, sec)
    m, s = divmod(sec, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h} ч {m} мин"
    return f"{m} мин {s} сек"


async def enqueue_voice_message(
    settings: Settings,
    tg: TelegramClient,
    chat_id: str,
    file_id: str,
    duration_sec: int,
    file_size: int,
    candidate_id: int | None,
    contact_name: str | None,
    mime_hint: str = "ogg",
) -> int:
    if duration_sec > settings.max_voice_duration_sec:
        await _panel_notify(
            tg,
            chat_id,
            f"Голосовое слишком длинное (макс. {settings.max_voice_duration_sec // 60} мин). "
            "Разбейте на несколько сообщений.",
        )
        return 0

    if file_size > settings.max_voice_bytes:
        await _panel_notify(tg, chat_id, "Файл больше 20 МБ — Telegram не поддерживает такие голосовые.")
        return 0

    total = estimate_total_chunks(duration_sec, settings.voice_chunk_seconds)
    job_id = await store.create_voice_job(
        chat_id=chat_id,
        file_id=file_id,
        duration_sec=duration_sec,
        file_size=file_size,
        total_chunks=total,
        candidate_id=candidate_id,
        contact_name=contact_name,
        mime_hint=mime_hint,
    )
    mins = _format_duration(duration_sec)
    await _panel_notify(
        tg,
        chat_id,
        f"🎙 <b>Голосовое получено</b> (~{mins})\n\n"
        f"⏳ Транскрибирую по частям: <b>0/{total}</b>\n"
        "Результат появится здесь же — можно закрыть чат.",
        None,
    )
    await trigger_voice_job(job_id, settings)
    return job_id


async def trigger_voice_job(job_id: int, settings: Settings) -> None:
    if not settings.webhook_base_url:
        logger.warning("WEBHOOK_BASE_URL not set — voice job %s waits for cron", job_id)
        return
    secret = settings.cron_secret or settings.admin_token
    url = f"{settings.webhook_base_url.rstrip('/')}/api/jobs/voice/{job_id}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(url, params={"secret": secret})
    except Exception as e:
        logger.warning("Voice job trigger %s: %s (cron will retry)", job_id, e)


async def process_voice_job_step(
    job_id: int,
    settings: Settings,
    tg: TelegramClient,
    llm,
) -> dict:
    job = await store.get_voice_job(job_id)
    if not job:
        return {"ok": False, "error": "not_found"}
    if job.status in ("done", "failed"):
        return {"ok": True, "status": job.status}

    if not settings.is_stt_configured:
        await store.fail_voice_job(job_id, "STT not configured")
        await _panel_notify(
            tg,
            job.chat_id,
            "Транскрипция недоступна: добавьте TOGETHER_API_KEY, GROQ_API_KEY или OPENAI_API_KEY.",
        )
        return {"ok": False, "error": "no_stt"}

    await store.mark_voice_job_processing(job_id)

    audio_bytes = await _load_voice_audio(tg, job)
    if not audio_bytes:
        await store.fail_voice_job(job_id, "download_failed")
        await _panel_notify(tg, job.chat_id, "Не удалось скачать голосовое. Отправьте ещё раз.")
        return {"ok": False, "error": "download"}

    fmt = "ogg" if "ogg" in (job.mime_hint or "") else "mpeg"
    chunk_bytes = extract_chunk_bytes(audio_bytes, job.chunk_index, settings.voice_chunk_seconds, fmt)
    if not chunk_bytes:
        await store.fail_voice_job(job_id, "chunk_empty")
        return {"ok": False, "error": "chunk_empty"}

    text = await transcribe_audio(settings, chunk_bytes, f"chunk_{job.chunk_index}.ogg")
    if not text:
        await store.fail_voice_job(job_id, f"transcribe_failed_chunk_{job.chunk_index}")
        await _panel_notify(
            tg,
            job.chat_id,
            f"❌ Ошибка транскрипции части {job.chunk_index + 1}/{job.total_chunks}. "
            "Попробуйте отправить короче.",
        )
        return {"ok": False, "error": "transcribe"}

    job = await store.append_voice_chunk(job_id, text)
    if not job:
        return {"ok": False, "error": "job_lost"}

    if job.chunk_index < job.total_chunks:
        await _panel_notify(
            tg,
            job.chat_id,
            f"🎙 <b>Транскрипция</b>\n\n"
            f"⏳ Обработано <b>{job.chunk_index}/{job.total_chunks}</b> частей…",
            None,
        )
        await trigger_voice_job(job_id, settings)
        return {"ok": True, "progress": f"{job.chunk_index}/{job.total_chunks}"}

    transcript = job.full_transcript()
    name = job.contact_name or "Кандидат"
    vacancy = await store.get_active_vacancy()
    profile = {}
    if llm and transcript:
        profile = await build_interview_profile(
            llm, transcript, name, vacancy.title if vacancy else ""
        )
    summary = profile.get("summary", transcript[:500] if transcript else "")
    cid = job.candidate_id or await store.upsert_candidate(
        source="telegram", chat_id=job.chat_id, name=name,
    )
    blob_url = job.audio_blob_url
    await store.save_interview_analysis(cid, transcript, summary, profile)
    await store.complete_voice_job(job_id)
    blob = get_blob_store()
    if blob_url:
        await blob.delete(blob_url)
    try:
        cache = _voice_cache_path(job_id)
        cache.unlink(missing_ok=True)
    except OSError:
        pass

    session = await store.get_session(job.chat_id)
    lang = session.lang or "ru"
    card = format_profile_card(profile, name) if profile else f"<b>Транскрипция</b>\n\n{transcript[:3500]}"
    await _panel_notify(tg, job.chat_id, card, confirm_keyboard(lang))
    await store.log_message(job.chat_id, "out", card[:2000], candidate_id=cid)
    await notify_hr_text(
        settings,
        tg,
        "📋 Карточка после интервью",
        f"Кандидат #{cid} {name}\nChat: <code>{job.chat_id}</code>\n\n{card[:3500]}",
    )
    return {"ok": True, "status": "done", "chars": len(transcript)}


def _voice_cache_path(job_id: int) -> Path:
    base = Path(os.environ.get("VOICE_CACHE_DIR", "/tmp/voice_cache"))
    base.mkdir(parents=True, exist_ok=True)
    return base / f"job_{job_id}.bin"


async def _load_voice_audio(tg: TelegramClient, job) -> bytes:
    blob = get_blob_store()
    if job.audio_blob_url and blob.available:
        data = await blob.get(job.audio_blob_url)
        if data:
            return data

    cache = _voice_cache_path(job.id)
    if cache.exists():
        return cache.read_bytes()

    data = await _download_voice(tg, job.file_id)
    if not data:
        return b""

    if blob.available:
        url = await blob.put_voice_audio(job.id, data, job.mime_hint or "audio/ogg")
        if url:
            await store.set_voice_job_blob(job.id, url)
    else:
        cache.write_bytes(data)
    return data


async def _download_voice(tg: TelegramClient, file_id: str) -> bytes:
    info = await tg.get_file(file_id)
    if not info:
        return b""
    path = info.get("result", {}).get("file_path")
    if not path:
        return b""
    return await tg.download_file(path)


async def process_stale_voice_jobs(settings: Settings, tg: TelegramClient, llm, limit: int = 2) -> int:
    jobs = await store.list_stale_voice_jobs(limit=limit)
    n = 0
    for job in jobs:
        await process_voice_job_step(job.id, settings, tg, llm)
        n += 1
    return n
