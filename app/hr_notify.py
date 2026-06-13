from __future__ import annotations

from typing import Any

from app.config import Settings
from app.storage.db import Session
from app.telegram_api import TelegramClient


def _fmt_profile(p: dict[str, Any]) -> str:
    lines = []
    if p.get("name"):
        lines.append(f"Имя: {p['name']}")
    if p.get("age") is not None:
        lines.append(f"Возраст: {p['age']}")
    if p.get("is_student") is not None:
        lines.append(f"Студент: {'да' if p['is_student'] else 'нет'}")
    if p.get("has_experience") is not None:
        lines.append(f"Опыт: {'да' if p['has_experience'] else 'нет'}")
    if p.get("city"):
        lines.append(f"Город: {p['city']}")
    return "\n".join(lines) if lines else "—"


async def notify_hr(
    settings: Settings,
    tg: TelegramClient,
    session: Session,
    event: str,
    extra: str = "",
) -> None:
    if not settings.is_hr_notify_configured:
        return
    chat = settings.telegram_hr_chat_id
    status_map = {
        "qualified": "✅ Подходит",
        "rejected": "❌ Отказ",
        "scheduled": "📅 Собеседование",
        "handoff": "👤 Передан HR",
        "no_show": "⚠️ Не придёт",
    }
    header = status_map.get(event, event)
    text = (
        f"<b>{header}</b>\n"
        f"Chat: <code>{session.chat_id}</code>\n"
        f"{_fmt_profile(session.profile)}\n"
    )
    if session.interview_label:
        text += f"Визит: {session.interview_label}\n"
    if session.contact_name:
        text += f"TG: {session.contact_name}\n"
    if extra:
        text += f"\n{extra}"
    await tg.send_message(chat, text, parse_mode="HTML")
