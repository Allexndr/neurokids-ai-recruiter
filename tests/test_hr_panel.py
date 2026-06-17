import pytest
from unittest.mock import AsyncMock, patch

from app.bot.hr_panel import handle_hr_panel
from app.config import Settings
from app.storage.db import Session


@pytest.fixture
def hr_session():
    return Session(chat_id="999", state="hr_panel", profile={"ui_mode": "hr"})


@pytest.fixture
def settings():
    return Settings(telegram_bot_token="x", telegram_hr_chat_id="999")


@pytest.mark.asyncio
async def test_hr_menu_callback(hr_session, settings):
    reply = await handle_hr_panel(hr_session, "hr:menu", is_callback=True, settings=settings, llm=None)
    assert reply is not None
    assert "Neurokids HR" in reply.text
    assert "hr:cands" in str(reply.reply_markup)


@pytest.mark.asyncio
async def test_hr_start_shows_menu(hr_session, settings):
    reply = await handle_hr_panel(hr_session, "/start", is_callback=False, settings=settings, llm=None)
    assert reply is not None
    assert reply.force_new is True
    assert "hr:rank" in str(reply.reply_markup)


@pytest.mark.asyncio
async def test_hr_slash_candidates_has_keyboard(hr_session, settings):
    with patch("app.bot.hr_panel.store") as mock_store:
        mock_store.list_candidates = AsyncMock(return_value=[])
        reply = await handle_hr_panel(hr_session, "/candidates", is_callback=False, settings=settings, llm=None)
    assert reply is not None
    assert "Кандидаты" in reply.text
    assert reply.reply_markup is not None


@pytest.mark.asyncio
async def test_hr_search_wait(hr_session, settings):
    reply = await handle_hr_panel(hr_session, "hr:search", is_callback=True, settings=settings, llm=None)
    assert "Поиск" in reply.text
    assert hr_session.profile.get("hr_wait") == "search"

    with patch("app.bot.hr_panel.handle_hr_command", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = "<b>Поиск: python</b>"
        reply2 = await handle_hr_panel(hr_session, "python dev", is_callback=False, settings=settings, llm=None)
    assert reply2 is not None
    mock_cmd.assert_awaited_once()
