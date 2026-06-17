from __future__ import annotations

from app.bot.scheduling import InterviewSlot, available_slots


def slots_keyboard(
    lang: str,
    tz: str = "Asia/Almaty",
    slots: list[InterviewSlot] | None = None,
) -> dict:
    items = slots if slots is not None else available_slots(tz_name=tz)
    rows: list[list[dict]] = []
    for s in items:
        label = s.label_kk if lang == "kk" else s.label_ru
        rows.append([{"text": f"🕐 {label[:60]}", "callback_data": f"slot:{s.slot_id}"}])
    back = "↩️ Мәзірге" if lang == "kk" else "↩️ Назад в меню"
    rows.append([{"text": back, "callback_data": "act:menu"}])
    return {"inline_keyboard": rows}

# Telegram: пустая inline-клавиатура снимает старые кнопки при editMessageText
CLEAR_KEYBOARD: dict = {"inline_keyboard": []}


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


def step_nav_keyboard(lang: str, *, back: str | None = None) -> dict:
    rows: list[list[dict]] = []
    if back:
        label = "↩️ Артқа" if lang == "kk" else "↩️ Назад"
        rows.append([{"text": label, "callback_data": back}])
    restart = "🔄 Қайта бастау" if lang == "kk" else "🔄 Начать заново"
    hr = "👤 HR" if lang == "kk" else "👤 Связаться с HR"
    rows.append(
        [
            {"text": restart, "callback_data": "act:restart"},
            {"text": hr, "callback_data": "act:human"},
        ]
    )
    return {"inline_keyboard": rows}


def main_menu_keyboard(lang: str) -> dict:
    if lang == "kk":
        return {
            "inline_keyboard": [
                [{"text": "📅 Собеседованиеге жазылу", "callback_data": "act:schedule"}],
                [{"text": "❓ Сұрақ қою", "callback_data": "act:faq"}],
                [{"text": "📄 Резюме жіберу", "callback_data": "act:resume"}],
            ]
        }
    return {
        "inline_keyboard": [
            [{"text": "📅 Записаться на собеседование", "callback_data": "act:schedule"}],
            [{"text": "❓ Задать вопрос", "callback_data": "act:faq"}],
            [{"text": "📄 Отправить резюме", "callback_data": "act:resume"}],
        ]
    }


def faq_topics_keyboard(lang: str) -> dict:
    if lang == "kk":
        return {
            "inline_keyboard": [
                [
                    {"text": "💰 Жалақы", "callback_data": "faq:salary"},
                    {"text": "📅 График", "callback_data": "faq:schedule"},
                ],
                [
                    {"text": "🎓 Тағылым", "callback_data": "faq:internship"},
                    {"text": "🏢 Neurokids", "callback_data": "faq:company"},
                ],
                [{"text": "📄 Резюме", "callback_data": "act:resume"}],
                [
                    {"text": "📅 Жазылу", "callback_data": "act:schedule"},
                    {"text": "↩️ Мәзір", "callback_data": "act:menu"},
                ],
            ]
        }
    return {
        "inline_keyboard": [
            [
                {"text": "💰 Зарплата", "callback_data": "faq:salary"},
                {"text": "📅 График", "callback_data": "faq:schedule"},
            ],
            [
                {"text": "🎓 Стажировка", "callback_data": "faq:internship"},
                {"text": "🏢 О компании", "callback_data": "faq:company"},
            ],
            [{"text": "📄 Резюме", "callback_data": "act:resume"}],
            [
                {"text": "📅 Записаться", "callback_data": "act:schedule"},
                {"text": "↩️ В меню", "callback_data": "act:menu"},
            ],
        ]
    }


def faq_keyboard(lang: str) -> dict:
    return faq_topics_keyboard(lang)


def resume_prompt_keyboard(lang: str) -> dict:
    if lang == "kk":
        return {
            "inline_keyboard": [
                [{"text": "↩️ Мәзірге", "callback_data": "act:menu"}],
            ]
        }
    return {
        "inline_keyboard": [
            [{"text": "↩️ В меню", "callback_data": "act:menu"}],
        ]
    }


def confirm_keyboard(lang: str) -> dict:
    if lang == "kk":
        return {
            "inline_keyboard": [
                [{"text": "❓ Сұрақ қою", "callback_data": "act:faq"}],
                [
                    {"text": "📅 Уақыт өзгерту", "callback_data": "act:schedule"},
                    {"text": "↩️ Мәзір", "callback_data": "act:menu"},
                ],
            ]
        }
    return {
        "inline_keyboard": [
            [{"text": "❓ Задать вопрос", "callback_data": "act:faq"}],
            [
                {"text": "📅 Изменить время", "callback_data": "act:schedule"},
                {"text": "↩️ В меню", "callback_data": "act:menu"},
            ],
        ]
    }


def handoff_keyboard(lang: str) -> dict:
    if lang == "kk":
        return {
            "inline_keyboard": [
                [{"text": "👤 HR-мен байланысу", "callback_data": "act:human"}],
                [{"text": "🔄 Қайта бастау", "callback_data": "act:restart"}],
            ]
        }
    return {
        "inline_keyboard": [
            [{"text": "👤 Связаться с HR", "callback_data": "act:human"}],
            [{"text": "🔄 Начать заново", "callback_data": "act:restart"}],
        ]
    }


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
