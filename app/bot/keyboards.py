from __future__ import annotations

from app.bot.scheduling import InterviewSlot, available_slots


def yes_no_keyboard(lang: str, prefix: str = "yn") -> dict:
    if lang == "kk":
        return {
            "inline_keyboard": [
                [
                    {"text": "✅ Иә", "callback_data": f"{prefix}:yes"},
                    {"text": "❌ Жоқ", "callback_data": f"{prefix}:no"},
                ],
            ]
        }
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Да", "callback_data": f"{prefix}:yes"},
                {"text": "❌ Нет", "callback_data": f"{prefix}:no"},
            ],
        ]
    }


def language_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "🇰🇿 Қазақша", "callback_data": "lang:kk"},
                {"text": "🇷🇺 Русский", "callback_data": "lang:ru"},
            ],
        ]
    }


def channel_view_keyboard(lang: str) -> dict:
    if lang == "kk":
        return {
            "inline_keyboard": [
                [
                    {"text": "📱 Telegram түрі", "callback_data": "view:telegram"},
                    {"text": "💬 WhatsApp түрі", "callback_data": "view:whatsapp"},
                ],
            ]
        }
    return {
        "inline_keyboard": [
            [
                {"text": "📱 Вид Telegram", "callback_data": "view:telegram"},
                {"text": "💬 Вид WhatsApp", "callback_data": "view:whatsapp"},
            ],
        ]
    }


def main_menu_keyboard(lang: str) -> dict:
    if lang == "kk":
        return {
            "inline_keyboard": [
                [
                    {"text": "📅 Собеседованиеге жазылу", "callback_data": "act:schedule"},
                    {"text": "❓ Сұрақ қою", "callback_data": "act:faq"},
                ],
            ]
        }
    return {
        "inline_keyboard": [
            [
                {"text": "📅 Записаться", "callback_data": "act:schedule"},
                {"text": "❓ Вопрос", "callback_data": "act:faq"},
            ],
        ]
    }


def slots_keyboard(lang: str, tz: str = "Asia/Almaty") -> dict:
    slots = available_slots(tz_name=tz)
    rows: list[list[dict]] = []
    row: list[dict] = []
    for s in slots:
        label = s.label_kk if lang == "kk" else s.label_ru
        row.append({"text": label[:64], "callback_data": f"slot:{s.slot_id}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "↩️" if lang == "kk" else "↩️ Назад", "callback_data": "act:menu"}])
    return {"inline_keyboard": rows}


def reminder_keyboard(lang: str) -> dict:
    if lang == "kk":
        return {
            "inline_keyboard": [
                [
                    {"text": "✅ Келемін", "callback_data": "rem:yes"},
                    {"text": "❌ Келе алмаймын", "callback_data": "rem:no"},
                ],
            ]
        }
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Приду", "callback_data": "rem:yes"},
                {"text": "❌ Не смогу", "callback_data": "rem:no"},
            ],
        ]
    }
