"""Единый шаблон шагов анкеты (правила + примеры)."""

from __future__ import annotations


def yes_no_step(
    *,
    step_no: int,
    title: str,
    question: str,
    rules: str,
    examples_ok: str,
    examples_bad: str,
    wa_hint: str = "",
) -> str:
    return (
        f"📋 <b>Шаг {step_no} — {title}</b>\n\n"
        f"{question}\n\n"
        f"📌 <b>Правила:</b> {rules}\n"
        + (f"{wa_hint}\n\n" if wa_hint else "\n")
        + f"💡 <b>Примеры:</b>\n"
        f"{examples_ok}\n\n"
        f"❌ <b>Не подходит:</b>\n"
        f"{examples_bad}"
    )


def text_step(
    *,
    step_no: int,
    title: str,
    question: str,
    rules: str,
    examples_ok: str,
    examples_bad: str,
) -> str:
    return (
        f"📋 <b>Шаг {step_no} — {title}</b>\n\n"
        f"{question}\n\n"
        f"📌 <b>Правила:</b>\n"
        f"{rules}\n\n"
        f"💡 <b>Примеры:</b>\n"
        f"{examples_ok}\n\n"
        f"❌ <b>Не подходит:</b>\n"
        f"{examples_bad}"
    )
