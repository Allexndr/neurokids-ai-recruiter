from __future__ import annotations

from typing import Any

from app.config import Settings
from app.storage.db import Session
from app.telegram_api import TelegramClient


def _fmt_profile(p: dict[str, Any]) -> str:
    lines = []
    if p.get("name"):
        lines.append(f"Имя: {p['name']}")
    if p.get("job_search_active") is not None:
        lines.append(f"Поиск работы: {'да' if p['job_search_active'] else 'нет'}")
    if p.get("experience_summary"):
        lines.append(f"Опыт: {p['experience_summary'][:200]}")
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
    status_map = {
        "qualified": "✅ Анкета принята",
        "rejected": "❌ Отказ",
        "scheduled": "📅 Собеседование записано",
        "confirmed": "✅ Кандидат подтвердил встречу",
        "handoff": "👤 Передан HR",
        "no_show": "⚠️ Не придёт",
        "reminder_24": "🔔 Напоминание 24ч отправлено",
        "reminder_1": "🔔 Напоминание 1ч отправлено",
        "interview_profile": "📋 Карточка после интервью",
        "hh_import": "📥 Новые отклики HH",
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
    if session.candidate_id:
        text += f"Кандидат: #{session.candidate_id}\n"
    if extra:
        text += f"\n{extra}"
    for chat in settings.hr_chat_ids:
        await tg.send_message(chat, text, parse_mode="HTML")


async def notify_hr_text(settings: Settings, tg: TelegramClient, title: str, body: str) -> None:
    if not settings.is_hr_notify_configured:
        return
    msg = f"<b>{title}</b>\n\n{body}"
    for chat in settings.hr_chat_ids:
        await tg.send_message(chat, msg, parse_mode="HTML")
