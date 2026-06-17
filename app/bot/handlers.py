from __future__ import annotations

import logging
from typing import Any

from app.bot.engine import BotEngine
from app.bot.hr_panel import deliver_hr_panel, handle_hr_panel
from app.bot.keyboards import main_menu_keyboard
from app.bot.outbound import deliver_bot_reply, update_panel
from app.config import Settings
from app.hr_notify import notify_hr
from app.interview.voice_processor import enqueue_voice_message
from app.storage import store
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


async def _handle_hr_update(
    body: dict[str, Any],
    chat_id: str,
    text: str,
    session,
    settings: Settings,
    tg: TelegramClient,
    llm,
    document: dict | None,
) -> None:
    is_callback = "callback_query" in body
    data = await _download_telegram_file(tg, document["file_id"]) if document else None
    fname = document.get("file_name", "file.pdf") if document else ""

    reply = await handle_hr_panel(
        session,
        text or "",
        is_callback=is_callback,
        settings=settings,
        llm=llm,
        document_bytes=data,
        document_name=fname,
    )
    if not reply:
        return

    if text and not is_callback:
        await store.log_message(chat_id, "in", text)
    elif is_callback and text:
        await store.log_message(chat_id, "in", f"[btn] {text}")

    await deliver_hr_panel(tg, session, chat_id, reply, body)
    await store.save_session(session)
    await store.log_message(chat_id, "out", reply.text[:2000])


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
        toast = "✓"
        if text and (
            text.startswith(("slot:", "faq:", "job:", "lang:", "rem:", "act:", "hr:"))
            or text.startswith("view:")
        ):
            toast = "✓"
        await tg.answer_callback_query(callback_id, text=toast)

    msg = body.get("message") or body.get("edited_message") or {}
    document = msg.get("document")
    voice = msg.get("voice") or msg.get("audio")

    session = await store.get_session(chat_id)
    if session.state == "choose_view":
        session.state = "choose_lang"
        session.profile["ui_mode"] = "telegram"
    if sender_name and not session.contact_name:
        session.contact_name = sender_name

    is_hr = settings.is_hr_chat(chat_id)

    if is_hr:
        await _handle_hr_update(body, chat_id, text or "", session, settings, tg, llm, document)
        return

    # Voice: queue long transcription (non-blocking webhook)
    if voice:
        file_id = voice.get("file_id", "")
        duration = int(voice.get("duration") or 0)
        file_size = int(voice.get("file_size") or msg.get("audio", {}).get("file_size") or 0)
        mime = "ogg"
        if msg.get("audio"):
            mime = msg["audio"].get("mime_type", "mpeg") or "mpeg"
        name = session.profile.get("name") or session.contact_name
        cid = session.candidate_id
        if not settings.is_stt_configured:
            from app.bot import content_ru as RU
            await update_panel(tg, session, chat_id, RU.FALLBACK_VOICE, None, body=body)
            await store.save_session(session)
            return
        await tg.send_chat_action(chat_id, "typing")
        await enqueue_voice_message(
            settings, tg, chat_id, file_id, duration, file_size, cid, name, mime_hint=mime,
        )
        await store.save_session(session)
        await store.log_message(chat_id, "in", "[voice]", candidate_id=cid)
        return

    if msg.get("audio"):
        from app.bot import content_ru as RU
        await update_panel(tg, session, chat_id, RU.FALLBACK_VOICE, None, body=body)
        await store.save_session(session)
        return

    # Candidate: resume upload
    if document:
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
            from app.storage.blob import get_blob_store

            blob = get_blob_store()
            blob_url = None
            if blob.available and data:
                blob_url = await blob.put_resume(cid, fname, data)
                if blob_url:
                    await store.upsert_candidate(
                        source="telegram", chat_id=chat_id, profile={**session.profile, "resume_blob_url": blob_url},
                    )
            session.candidate_id = cid
            session.profile["resume_uploaded"] = True
            session.profile.pop("awaiting_resume", None)
            session.profile["experience_summary"] = resume_text[:2000]
            if session.profile.get("lang_locked"):
                session.state = "welcome_qualified"
            await store.save_session(session)
            reply_text = f"✅ Резюме получено. Оценка соответствия: {score or '—'}/100\n{summary or ''}"
            menu_kb = main_menu_keyboard(session.lang or "ru")
            await update_panel(tg, session, chat_id, reply_text, menu_kb, body=body)
            await store.save_session(session)
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

    if reply.stat:
        await store.bump_stat(reply.stat)

    force_new = text.strip() in ("/start", "/reset")
    await deliver_bot_reply(tg, session, chat_id, reply, body, force_new=force_new)
    await store.save_session(session)
    await store.log_message(chat_id, "out", reply.text, candidate_id=session.candidate_id)

    if reply.notify_hr:
        await notify_hr(settings, tg, session, reply.notify_hr)
