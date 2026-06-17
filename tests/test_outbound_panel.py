import pytest
from unittest.mock import AsyncMock, MagicMock

from app.bot.engine import BotEngine
from app.bot.keyboards import CLEAR_KEYBOARD, confirm_keyboard, faq_keyboard
from app.bot.outbound import deliver_bot_reply, effective_markup, update_panel
from app.bot.states import State
from app.config import Settings
from app.storage.db import Session


@pytest.fixture
def tg():
    client = MagicMock()
    client.edit_message = AsyncMock(return_value=True)
    client.send_message = AsyncMock(return_value={"ok": True, "result": {"message_id": 99}})
    client.delete_message = AsyncMock(return_value=True)
    client.extract_panel_message_id = MagicMock(return_value=42)
    return client


def test_effective_markup_clears_on_telegram():
    session = Session(chat_id="1", state=State.COLLECT_NAME_AGE.value, profile={"ui_mode": "telegram"})
    assert effective_markup(session, None) == CLEAR_KEYBOARD


def test_effective_markup_none_on_whatsapp():
    session = Session(chat_id="1", state=State.COLLECT_NAME_AGE.value, profile={"ui_mode": "whatsapp"})
    assert effective_markup(session, None) is None


@pytest.mark.asyncio
async def test_update_panel_edits_existing(tg):
    session = Session(
        chat_id="1",
        state=State.WELCOME_QUALIFIED.value,
        profile={"ui_mode": "telegram", "panel_message_id": 42},
    )
    body = {"callback_query": {"message": {"message_id": 42}}}
    mid = await update_panel(tg, session, "1", "Привет", faq_keyboard("ru"), body=body)
    assert mid == 42
    tg.edit_message.assert_awaited_once()
    tg.send_message.assert_not_awaited()
    assert session.profile["panel_message_id"] == 42


@pytest.mark.asyncio
async def test_update_panel_deletes_and_resends_on_edit_fail(tg):
    tg.edit_message = AsyncMock(return_value=False)
    session = Session(
        chat_id="1",
        state=State.WELCOME_QUALIFIED.value,
        profile={"ui_mode": "telegram", "panel_message_id": 7},
    )
    mid = await update_panel(tg, session, "1", "Новый текст", faq_keyboard("ru"))
    assert mid == 99
    tg.delete_message.assert_awaited_once_with("1", 7)
    tg.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_deliver_bot_reply_clears_keyboard_when_none(tg):
    session = Session(
        chat_id="1",
        state=State.COLLECT_NAME_AGE.value,
        profile={"ui_mode": "telegram", "panel_message_id": 5},
    )
    from app.bot.engine import EngineReply

    reply = EngineReply("Введите имя", reply_markup=None)
    await deliver_bot_reply(tg, session, "1", reply, {})
    tg.edit_message.assert_awaited_once()
    assert tg.edit_message.await_args.kwargs["reply_markup"] == CLEAR_KEYBOARD


@pytest.mark.asyncio
async def test_faq_callback_has_inline_buttons():
    settings = Settings(telegram_bot_token="x", fallback_attempts_max=2)
    engine = BotEngine(settings, None, MagicMock())
    session = Session(
        chat_id="1",
        state=State.WELCOME_QUALIFIED.value,
        lang="ru",
        profile={"ui_mode": "telegram", "lang_locked": True, "name": "Айым"},
    )
    reply = await engine.handle(session, "act:faq", is_callback=True)
    assert reply.reply_markup is not None
    assert "act:menu" in str(reply.reply_markup)


@pytest.mark.asyncio
async def test_slot_confirm_has_menu_buttons():
    settings = Settings(telegram_bot_token="x", fallback_attempts_max=2, bot_timezone="Asia/Almaty")
    engine = BotEngine(settings, None, MagicMock())
    session = Session(
        chat_id="1",
        state=State.SCHEDULE_INTERVIEW.value,
        lang="ru",
        profile={"ui_mode": "telegram", "lang_locked": True, "name": "Айым"},
    )
    from app.bot.scheduling import available_slots

    slots = available_slots(tz_name="Asia/Almaty")
    assert slots
    reply = await engine.handle(session, f"slot:{slots[0].slot_id}", is_callback=True)
    assert session.state == State.CONFIRM.value
    assert reply.reply_markup == confirm_keyboard("ru")


@pytest.mark.asyncio
async def test_reminder_yes_keeps_panel_buttons():
    settings = Settings(telegram_bot_token="x")
    engine = BotEngine(settings, None, MagicMock())
    session = Session(
        chat_id="1",
        state=State.CONFIRM.value,
        lang="ru",
        profile={"ui_mode": "telegram", "lang_locked": True},
    )
    reply = await engine.handle(session, "rem:yes", is_callback=True)
    assert reply.reply_markup == confirm_keyboard("ru")
