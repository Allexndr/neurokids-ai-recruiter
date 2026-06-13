from __future__ import annotations

import logging
from typing import Any

from app.bot.engine import BotEngine
from app.bot.hr_commands import handle_hr_command
from app.bot.outbound import deliver_bot_reply
from app.config import Settings
from app.hr_notify import notify_hr
from app.interview.profile_builder import build_interview_profile, format_profile_card
from app.interview.transcribe import transcribe_audio
from app.storage.db import store
from app.telegram_api import TelegramClient, detect_message_lang, extract_update_info

logger = logging.getLogger(__name__)


async def _download_telegram_file(tg: TelegramClient, file_id: str) -> bytes:
    info = await tg.get_file(file_id)
    if not info:
        return b""
    path = info.get("result", {}).get("file_path")
    if not path:
        return b""
    return await tg.download_file(path)


async def handle_telegram_update(
    body: dict[str, Any],
    settings: Settings,
    tg: TelegramClient,
    engine: BotEngine,
    llm=None,
) -> None:
    chat_id, text, sender_name, callback_id = extract_update_info(body)
    if not chat_id:
        return

    if callback_id:
        await tg.answer_callback_query(callback_id)

    msg = body.get("message") or body.get("edited_message") or {}
    document = msg.get("document")
    voice = msg.get("voice") or msg.get("audio")

    session = await store.get_session(chat_id)
    if sender_name and not session.contact_name:
        session.contact_name = sender_name

    is_hr = settings.is_hr_chat(chat_id)

    # HR: documents + commands
    if is_hr and document:
        file_id = document.get("file_id", "")
        fname = document.get("file_name", "file.pdf")
        data = await _download_telegram_file(tg, file_id)
        cmd = (text or "/import_resume").strip()
        reply = await handle_hr_command(cmd, chat_id, settings, llm, document_bytes=data, document_name=fname)
        if reply:
            await tg.send_message(chat_id, reply, parse_mode="HTML")
            await store.log_message(chat_id, "out", reply)
        return

    if is_hr and text and text.strip().startswith("/"):
        reply = await handle_hr_command(text, chat_id, settings, llm)
        if reply:
            await tg.send_message(chat_id, reply, parse_mode="HTML")
            await store.log_message(chat_id, "out", reply)
        return

    # Voice: interview transcription (HR or qualified candidate)
    if voice and llm:
        file_id = voice.get("file_id", "")
        data = await _download_telegram_file(tg, file_id)
        if data:
            transcript = await transcribe_audio(settings, data, "voice.ogg")
            if transcript:
                name = session.profile.get("name") or session.contact_name or "Кандидат"
                vacancy = await store.get_active_vacancy()
                profile = await build_interview_profile(
                    llm, transcript, name, vacancy.title if vacancy else ""
                )
                summary = profile.get("summary", transcript[:300])
                cid = session.candidate_id or await store.upsert_candidate(
                    source="telegram", chat_id=chat_id, name=name, profile=session.profile,
                )
                session.candidate_id = cid
                await store.save_interview_analysis(cid, transcript, summary, profile)
                card = format_profile_card(profile, name)
                await tg.send_message(chat_id, card, parse_mode="HTML")
                if is_hr and settings.is_hr_notify_configured:
                    await notify_hr(settings, tg, session, "qualified", extra=card[:500])
                await store.log_message(chat_id, "out", card, candidate_id=cid)
                return

    if voice or msg.get("audio"):
        from app.bot import content_ru as RU
        lang = session.lang or "ru"
        await tg.send_message(chat_id, RU.FALLBACK_VOICE)
        return

    # Candidate: resume upload
    if document and not is_hr:
        from app.sourcing.resume_parser import extract_text_from_bytes
        from app.sourcing.scorer import score_resume

        file_id = document.get("file_id", "")
        fname = document.get("file_name", "")
        data = await _download_telegram_file(tg, file_id)
        resume_text = extract_text_from_bytes(data, fname)
        if resume_text:
            vacancy = await store.get_active_vacancy()
            score, summary = None, None
            if llm and vacancy:
                result = await score_resume(llm, vacancy.title, vacancy.criteria, resume_text)
                score = result.get("score")
                summary = result.get("summary")
            cid = await store.upsert_candidate(
                source="telegram", chat_id=chat_id,
                name=session.profile.get("name"), resume_text=resume_text,
                vacancy_id=vacancy.id if vacancy else None,
                match_score=score, match_summary=summary, profile=session.profile,
            )
            session.candidate_id = cid
            session.profile["resume_uploaded"] = True
            await store.save_session(session)
            reply_text = f"✅ Резюме получено. Оценка соответствия: {score or '—'}/100\n{summary or ''}"
            await tg.send_message(chat_id, reply_text)
            await store.log_message(chat_id, "out", reply_text, candidate_id=cid)
            return

    is_callback = "callback_query" in body
    text = text or ""

    if text and not is_callback:
        if session.state not in ("choose_view", "choose_lang") or session.profile.get("lang_locked"):
            session.lang = detect_message_lang(text) or session.lang
        await store.log_message(chat_id, "in", text, candidate_id=session.candidate_id)

    if text.strip() in ("/start", "/reset"):
        session = await store.reset_session(chat_id)
        if sender_name:
            session.contact_name = sender_name
        session.profile.pop("panel_message_id", None)

    if llm and len(text) > 40:
        await tg.send_chat_action(chat_id, "typing")

    reply = await engine.handle(session, text, is_callback=is_callback)
    await store.save_session(session)

    if reply.stat:
        await store.bump_stat(reply.stat)

    force_new = text.strip() in ("/start", "/reset")
    await deliver_bot_reply(tg, session, chat_id, reply, body, force_new=force_new)
    await store.log_message(chat_id, "out", reply.text, candidate_id=session.candidate_id)

    if reply.notify_hr:
        await notify_hr(settings, tg, session, reply.notify_hr)
