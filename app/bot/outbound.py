"""Доставка ответов: одно сообщение в Telegram-виде, новые — в WhatsApp-виде."""

from __future__ import annotations

import logging
from typing import Any

from app.bot.channel_ui import is_whatsapp_ui
from typing import TYPE_CHECKING

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
    }
)


def use_telegram_panel(session: Session) -> bool:
    if is_whatsapp_ui(session):
        return False
    return session.state in PANEL_STATES or not session.profile.get("ui_mode")


async def deliver_bot_reply(
    tg: TelegramClient,
    session: Session,
    chat_id: str,
    reply: "EngineReply",
    body: dict[str, Any],
    *,
    force_new: bool = False,
) -> None:
    if not use_telegram_panel(session) or force_new:
        result = await tg.send_message(chat_id, reply.text, reply_markup=reply.reply_markup)
        if result and result.get("ok") and use_telegram_panel(session):
            mid = (result.get("result") or {}).get("message_id")
            if mid is not None:
                session.profile["panel_message_id"] = int(mid)
        return

    msg_id = tg.extract_panel_message_id(body)
    if msg_id is None:
        stored = session.profile.get("panel_message_id")
        if stored is not None:
            msg_id = int(stored)

    if msg_id is not None:
        ok = await tg.edit_message(
            chat_id,
            msg_id,
            reply.text,
            reply_markup=reply.reply_markup,
        )
        if ok:
            session.profile["panel_message_id"] = msg_id
            return
        logger.warning("editMessage failed chat=%s msg=%s, sending new", chat_id, msg_id)

    result = await tg.send_message(chat_id, reply.text, reply_markup=reply.reply_markup)
    if result and result.get("ok"):
        mid = (result.get("result") or {}).get("message_id")
        if mid is not None:
            session.profile["panel_message_id"] = int(mid)
