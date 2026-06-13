import pytest
from unittest.mock import MagicMock

from app.bot.engine import BotEngine
from app.bot.states import State
from app.config import Settings
from app.storage.db import Session


@pytest.fixture
def engine():
    settings = Settings(telegram_bot_token="x", fallback_attempts_max=2)
    return BotEngine(settings, None, MagicMock())


@pytest.mark.asyncio
async def test_start_shows_view_choice(engine):
    session = Session(chat_id="1", state=State.CHOOSE_VIEW.value)
    reply = await engine.handle(session, "/start")
    assert "Telegram" in reply.text or "WhatsApp" in reply.text
    assert reply.reply_markup is not None
    assert session.state == State.CHOOSE_VIEW.value


@pytest.mark.asyncio
async def test_view_then_lang_then_greeting(engine):
    session = Session(chat_id="3", state=State.CHOOSE_VIEW.value)
    await engine.handle(session, "1")
    assert session.profile.get("ui_mode") == "telegram"
    assert session.state == State.CHOOSE_LANG.value
    reply = await engine.handle(session, "2")
    assert session.lang == "ru"
    assert session.profile.get("lang_locked")
    assert "Здравствуйте" in reply.text or "менеджер" in reply.text.lower()


@pytest.mark.asyncio
async def test_whatsapp_view_no_buttons_on_menu(engine):
    session = Session(chat_id="2", state=State.CHOOSE_VIEW.value, lang="ru")
    await engine.handle(session, "2")
    assert session.profile.get("ui_mode") == "whatsapp"
    await engine.handle(session, "1")
    session.state = State.WELCOME_QUALIFIED.value
    session.profile["name"] = "Айым"
    session.profile["lang_locked"] = True
    reply = await engine.handle(session, "1")
    assert reply.reply_markup is None
    assert "1 —" in reply.text or "Уақыт" in reply.text or "Выберите" in reply.text
