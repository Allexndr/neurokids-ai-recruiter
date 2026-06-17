"""HR-панель: одно сообщение + inline-кнопки (команды / сохранены)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.bot.hr_commands import handle_hr_command
from app.bot.hr_keyboards import (
    hr_candidate_keyboard,
    hr_candidates_keyboard,
    hr_main_keyboard,
    hr_nav_keyboard,
    hr_vacancies_keyboard,
)
from app.bot.outbound import update_panel
from app.config import Settings
from app.storage import Session, store
from app.telegram_api import TelegramClient

HR_MENU_TEXT = (
    "<b>Neurokids HR</b> — панель рекрутера\n\n"
    "Все действия — кнопками ниже 👇\n"
    "<i>Команды / тоже работают</i>"
)

HR_START_TRIGGERS = frozenset({"/start", "/hr", "/help", "/reset"})


@dataclass
class HrPanelReply:
    text: str
    reply_markup: dict | None = None
    force_new: bool = False


def _clear_wait(session: Session) -> None:
    session.profile.pop("hr_wait", None)


def _set_wait(session: Session, kind: str, payload: str = "") -> None:
    session.profile["hr_wait"] = f"{kind}:{payload}" if payload else kind


async def handle_hr_panel(
    session: Session,
    text: str,
    *,
    is_callback: bool,
    settings: Settings,
    llm: Any,
    document_bytes: bytes | None = None,
    document_name: str = "",
) -> HrPanelReply | None:
    t = (text or "").strip()
    session.state = "hr_panel"
    session.profile["ui_mode"] = "hr"

    if document_bytes:
        wait = session.profile.get("hr_wait", "")
        if wait == "import:csv":
            cmd = "/import_csv"
        else:
            cmd = "/import_resume"
        _clear_wait(session)
        body = await handle_hr_command(
            cmd, session.chat_id, settings, llm,
            document_bytes=document_bytes, document_name=document_name,
        )
        if not body:
            return HrPanelReply("Не удалось импортировать файл.", hr_main_keyboard())
        return HrPanelReply(body, hr_main_keyboard())

    if is_callback and t.startswith("hr:"):
        return await _handle_hr_callback(session, t, settings, llm)

    if t in HR_START_TRIGGERS or (is_callback and t == "hr:menu"):
        _clear_wait(session)
        return HrPanelReply(HR_MENU_TEXT, hr_main_keyboard(), force_new=t in ("/start", "/reset"))

    wait = session.profile.get("hr_wait")
    if wait and t and not t.startswith("/"):
        return await _handle_hr_wait(session, t, wait, settings, llm)

    if t.startswith("/"):
        body = await handle_hr_command(t, session.chat_id, settings, llm)
        if not body:
            return None
        kb = _keyboard_for_slash(t)
        return HrPanelReply(body, kb)

    if t:
        return HrPanelReply(
            "Выберите действие кнопкой ниже 👇\n\n<i>Или используйте команды /</i>",
            hr_main_keyboard(),
        )

    return HrPanelReply(HR_MENU_TEXT, hr_main_keyboard())


def _keyboard_for_slash(cmd: str) -> dict:
    low = cmd.lower().strip()
    if low.startswith("/candidate ") and len(low.split()) >= 2 and low.split()[1].isdigit():
        return hr_candidate_keyboard(int(low.split()[1]))
    if low.startswith("/candidates"):
        return hr_nav_keyboard()
    return hr_main_keyboard()


async def _handle_hr_wait(
    session: Session,
    text: str,
    wait: str,
    settings: Settings,
    llm: Any,
) -> HrPanelReply:
    _clear_wait(session)
    if wait == "search":
        body = await handle_hr_command(f"/search {text}", session.chat_id, settings, llm)
        return HrPanelReply(body or "Ничего не найдено.", hr_nav_keyboard())
    if wait == "compare":
        parts = text.replace(",", " ").split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            body = await handle_hr_command(f"/compare {parts[0]} {parts[1]}", session.chat_id, settings, llm)
            return HrPanelReply(body or "Ошибка сравнения.", hr_nav_keyboard())
        return HrPanelReply("Формат: <code>5 12</code> (два ID)", hr_nav_keyboard())
    if wait.startswith("comment:"):
        cid = wait.split(":", 1)[1]
        body = await handle_hr_command(f"/comment {cid} {text}", session.chat_id, settings, llm)
        return HrPanelReply(body or "Ошибка.", hr_candidate_keyboard(int(cid)))
    return HrPanelReply(HR_MENU_TEXT, hr_main_keyboard())


async def _handle_hr_callback(
    session: Session,
    data: str,
    settings: Settings,
    llm: Any,
) -> HrPanelReply:
    _clear_wait(session)

    if data == "hr:menu":
        return HrPanelReply(HR_MENU_TEXT, hr_main_keyboard())

    if data == "hr:help":
        body = await handle_hr_command("/help", session.chat_id, settings, llm)
        return HrPanelReply(body or "", hr_main_keyboard())

    if data == "hr:cands":
        cands = await store.list_candidates(limit=15)
        if not cands:
            return HrPanelReply("Кандидатов пока нет.", hr_main_keyboard())
        lines = ["<b>Кандидаты</b> — нажмите для карточки 👇"]
        return HrPanelReply("\n".join(lines), hr_candidates_keyboard(cands))

    if data.startswith("hr:cands:"):
        vid = int(data.split(":")[2])
        cands = await store.list_candidates(vacancy_id=vid, limit=15)
        if not cands:
            return HrPanelReply(f"Нет кандидатов по вакансии #{vid}.", hr_vacancies_keyboard(await store.list_vacancies(active_only=False)))
        return HrPanelReply(f"<b>Вакансия #{vid}</b> — кандидаты:", hr_candidates_keyboard(cands))

    if data.startswith("hr:cand:"):
        cid = int(data.split(":")[2])
        body = await handle_hr_command(f"/candidate {cid}", session.chat_id, settings, llm)
        return HrPanelReply(body or "Не найден.", hr_candidate_keyboard(cid))

    if data == "hr:rank":
        body = await handle_hr_command("/rank", session.chat_id, settings, llm)
        return HrPanelReply(body or "Нет данных.", hr_nav_keyboard())

    if data == "hr:vac":
        vacs = await store.list_vacancies(active_only=False)
        if not vacs:
            return HrPanelReply(
                "Вакансий нет.\nСоздайте: <code>/vacancy create Менеджер | продажи, CRM</code>",
                hr_main_keyboard(),
            )
        lines = ["<b>Вакансии</b> — нажмите, чтобы увидеть кандидатов 👇"]
        return HrPanelReply("\n".join(lines), hr_vacancies_keyboard(vacs))

    if data == "hr:stats":
        body = await handle_hr_command("/stats", session.chat_id, settings, llm)
        return HrPanelReply(body or "Пусто.", hr_nav_keyboard())

    if data == "hr:sync":
        body = await handle_hr_command("/hh_sync", session.chat_id, settings, llm)
        return HrPanelReply(body or "Готово.", hr_nav_keyboard())

    if data == "hr:search":
        _set_wait(session, "search")
        return HrPanelReply(
            "🔍 <b>Поиск</b>\n\nНапишите запрос одним сообщением.\n<i>Или: /search python менеджер</i>",
            hr_nav_keyboard(),
        )

    if data == "hr:cmp":
        _set_wait(session, "compare")
        return HrPanelReply(
            "⚖️ <b>Сравнение</b>\n\nНапишите два ID: <code>5 12</code>\n<i>Или: /compare 5 12</i>",
            hr_nav_keyboard(),
        )

    if data == "hr:imp:resume":
        _set_wait(session, "import", "resume")
        return HrPanelReply(
            "📄 <b>Импорт резюме</b>\n\nПрикрепите PDF или DOCX.\n<i>Или: /import_resume + файл</i>",
            hr_nav_keyboard(),
        )

    if data == "hr:imp:csv":
        _set_wait(session, "import", "csv")
        return HrPanelReply(
            "📊 <b>Импорт CSV</b>\n\nПрикрепите CSV (name, phone, resume).\n<i>Или: /import_csv + файл</i>",
            hr_nav_keyboard(),
        )

    if data.startswith("hr:out:"):
        cid = data.split(":")[2]
        body = await handle_hr_command(f"/outreach {cid}", session.chat_id, settings, llm)
        return HrPanelReply(body or "Ошибка.", hr_candidate_keyboard(int(cid)))

    if data.startswith("hr:comm:"):
        cid = data.split(":")[2]
        _set_wait(session, "comment", cid)
        return HrPanelReply(
            f"💬 Комментарий к #{cid}\n\nНапишите текст.\n<i>Или: /comment {cid} текст</i>",
            hr_candidate_keyboard(int(cid)),
        )

    return HrPanelReply(HR_MENU_TEXT, hr_main_keyboard())


async def deliver_hr_panel(
    tg: TelegramClient,
    session: Session,
    chat_id: str,
    reply: HrPanelReply,
    body: dict[str, Any] | None,
) -> None:
    await update_panel(
        tg,
        session,
        chat_id,
        reply.text,
        reply.reply_markup,
        body=body,
        force_new=reply.force_new,
    )
