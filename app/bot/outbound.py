"""Доставка ответов: одно редактируемое сообщение в Telegram-виде."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.bot.channel_ui import is_whatsapp_ui
from app.bot.keyboards import CLEAR_KEYBOARD
from app.storage.db import Session
from app.telegram_api import TelegramClient

if TYPE_CHECKING:
    from app.bot.engine import EngineReply

logger = logging.getLogger(__name__)

PANEL_STATES = frozenset(
    {
        "choose_view",
        "choose_lang",
        "collect_name_age",
        "collect_student",
        "collect_experience",
        "collect_profile",
        "collect_city",
        "collect_schedule",
        "student_schedule",
        "collect_language",
        "welcome_qualified",
        "qa",
        "schedule_interview",
        "confirm",
        "rejected",
        "handoff_hr",
        "closed",
        "hr_panel",
    }
)


def use_telegram_panel(session: Session) -> bool:
    if is_whatsapp_ui(session):
        return False
    if session.state == "hr_panel" or session.profile.get("ui_mode") == "hr":
        return True
    return session.state in PANEL_STATES or not session.profile.get("ui_mode")


def effective_markup(session: Session, reply_markup: dict | None) -> dict | None:
    """Telegram-панель: None → снять кнопки. WhatsApp: без клавиатуры."""
    if is_whatsapp_ui(session):
        return None
    if reply_markup is not None:
        return reply_markup
    return CLEAR_KEYBOARD


def _panel_message_id(session: Session, body: dict[str, Any] | None, tg: TelegramClient) -> int | None:
    if body:
        mid = tg.extract_panel_message_id(body)
        if mid is not None:
            return mid
    stored = session.profile.get("panel_message_id")
    return int(stored) if stored is not None else None


async def update_panel(
    tg: TelegramClient,
    session: Session,
    chat_id: str,
    text: str,
    reply_markup: dict | None = None,
    *,
    body: dict[str, Any] | None = None,
    force_new: bool = False,
) -> int | None:
    """Редактировать панель или отправить новую. Возвращает message_id."""
    panel_mode = use_telegram_panel(session)
    markup = effective_markup(session, reply_markup) if panel_mode else reply_markup

    if not panel_mode or force_new:
        result = await tg.send_message(chat_id, text, reply_markup=reply_markup)
        if result and result.get("ok"):
            mid = (result.get("result") or {}).get("message_id")
            if mid is not None and panel_mode:
                session.profile["panel_message_id"] = int(mid)
            return int(mid) if mid is not None else None
        return None

    msg_id = _panel_message_id(session, body, tg)
    if msg_id is not None and not force_new:
        ok = await tg.edit_message(chat_id, msg_id, text, reply_markup=markup)
        if ok:
            session.profile["panel_message_id"] = msg_id
            return msg_id
        logger.warning("editMessage failed chat=%s msg=%s — replace panel", chat_id, msg_id)
        await tg.delete_message(chat_id, msg_id)
        session.profile.pop("panel_message_id", None)

    result = await tg.send_message(chat_id, text, reply_markup=markup)
    if result and result.get("ok"):
        mid = (result.get("result") or {}).get("message_id")
        if mid is not None:
            session.profile["panel_message_id"] = int(mid)
            return int(mid)
    return None


async def deliver_bot_reply(
    tg: TelegramClient,
    session: Session,
    chat_id: str,
    reply: "EngineReply",
    body: dict[str, Any],
    *,
    force_new: bool = False,
) -> None:
    await update_panel(
        tg,
        session,
        chat_id,
        reply.text,
        reply.reply_markup,
        body=body,
        force_new=force_new,
    )
