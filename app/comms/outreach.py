"""Исходящий контакт с кандидатом (модуль 2 ТЗ)."""

from __future__ import annotations

from app.bot import content_boot as BOOT
from app.bot.keyboards import language_keyboard
from app.bot.states import State
from app.storage import Session, store
from app.telegram_api import TelegramClient


async def send_telegram_outreach(tg: TelegramClient, chat_id: str) -> bool:
    """Приглашение кандидата в бот (если известен Telegram chat_id)."""
    session = await store.get_session(chat_id)
    session.state = State.CHOOSE_LANG.value
    session.profile = {"ui_mode": "telegram", "outreach": True}
    session.status = "outreach"
    session.clarify_attempts = 0
    await store.save_session(session)
    result = await tg.send_message(chat_id, BOOT.WELCOME_START, reply_markup=language_keyboard())
    return bool(result and result.get("ok"))
