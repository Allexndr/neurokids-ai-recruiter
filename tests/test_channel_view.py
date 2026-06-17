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
async def test_start_shows_neurokids_language_choice(engine):
    session = Session(chat_id="1", state="choose_view")
    reply = await engine.handle(session, "/start")
    assert "Neurokids" in reply.text
    assert "Атаман" not in reply.text
    assert "WhatsApp" not in reply.text
    assert session.state == State.CHOOSE_LANG.value
    assert session.profile.get("ui_mode") == "telegram"
    assert reply.reply_markup is not None


@pytest.mark.asyncio
async def test_legacy_view_callback_resets_to_language(engine):
    session = Session(chat_id="2", state="choose_view", profile={"ui_mode": "whatsapp"})
    reply = await engine.handle(session, "view:telegram", is_callback=True)
    assert "Neurokids" in reply.text
    assert "Атаман" not in reply.text
    assert session.state == State.CHOOSE_LANG.value
    assert session.profile.get("ui_mode") == "telegram"


@pytest.mark.asyncio
async def test_lang_then_questionnaire(engine):
    session = Session(chat_id="3", state=State.CHOOSE_LANG.value, profile={"ui_mode": "telegram"})
    reply = await engine.handle(session, "lang:ru", is_callback=True)
    assert session.lang == "ru"
    assert session.profile.get("lang_locked")
    assert session.state == State.COLLECT_NAME_AGE.value
    assert "Neurokids" in reply.text
    assert "Шаг 1" in reply.text or "имя" in reply.text.lower()


@pytest.mark.asyncio
async def test_whatsapp_view_no_buttons_on_menu(engine):
    session = Session(chat_id="4", state=State.CHOOSE_LANG.value, lang="ru", profile={"ui_mode": "whatsapp"})
    session.profile["lang_locked"] = True
    session.state = State.WELCOME_QUALIFIED.value
    session.profile["name"] = "Айым"
    reply = await engine.handle(session, "1")
    assert reply.reply_markup is None
    assert "1 —" in reply.text or "Уақыт" in reply.text or "Выберите" in reply.text
