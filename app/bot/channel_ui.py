"""UI mode: Telegram (buttons) vs WhatsApp (text/numbers demo)."""

from __future__ import annotations

from app.bot.scheduling import InterviewSlot, available_slots
from app.storage.db import Session


def ui_mode(session: Session) -> str:
    return (session.profile.get("ui_mode") or "telegram").lower()


def is_whatsapp_ui(session: Session) -> bool:
    return ui_mode(session) == "whatsapp"


def parse_lang_choice(text: str) -> str | None:
    t = (text or "").lower().strip()
    if t in ("1", "kk", "kz", "kaz", "қазақ", "казах", "қазақша", "казахский"):
        return "kk"
    if t in ("2", "ru", "rus", "рус", "русский", "орысша"):
        return "ru"
    if any(x in t for x in ("қазақ", "казах", "kk")):
        return "kk"
    if any(x in t for x in ("рус", "rus", "ru")):
        return "ru"
    return None


def parse_view_choice(text: str) -> str | None:
    t = (text or "").lower().strip()
    if t in ("1", "telegram", "телеграм", "tg", "📱"):
        return "telegram"
    if t in ("2", "whatsapp", "ватсап", "вацап", "wa", "вотсап", "💬"):
        return "whatsapp"
    if "telegram" in t or "телеграм" in t:
        return "telegram"
    if "whatsapp" in t or "ватс" in t or "вацап" in t:
        return "whatsapp"
    return None


def wa_main_menu_text(lang: str) -> str:
    if lang == "kk":
        return "Мәзір:\n1 — Собеседованиеге жазылу\n2 — Сұрақ қою\n\nСанын жазыңыз."
    return "Меню:\n1 — Записаться на собеседование\n2 — Задать вопрос\n\nНапишите цифру."


def wa_slots_text(lang: str, tz: str = "Asia/Almaty") -> str:
    slots = available_slots(tz_name=tz)
    lines = ["Уақытты таңдаңыз (сан):" if lang == "kk" else "Выберите время (цифра):"]
    for i, s in enumerate(slots, start=1):
        label = s.label_kk if lang == "kk" else s.label_ru
        lines.append(f"{i} — {label}")
    lines.append("0 — артқа" if lang == "kk" else "0 — назад")
    return "\n".join(lines)


def wa_reminder_text(lang: str) -> str:
    if lang == "kk":
        return "Келесіз бе?\n1 — Иә, келемін\n2 — Жоқ, келе алмаймын"
    return "Придёте?\n1 — Да\n2 — Нет"


def slot_index_choice(text: str, lang: str, tz: str) -> InterviewSlot | None:
    t = text.strip()
    if t in ("0", "назад", "артқа", "back"):
        return None
    if not t.isdigit():
        return None
    idx = int(t)
    slots = available_slots(tz_name=tz)
    if 1 <= idx <= len(slots):
        return slots[idx - 1]
    return None
