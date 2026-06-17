import pytest

from app.bot.faq import keyword_faq


@pytest.mark.asyncio
async def test_percent_kk():
    ans = keyword_faq("Қанша %?", "kk")
    assert ans and ("собеседование" in ans.lower() or "жалақы" in ans.lower())


def test_salary_ru():
    ans = keyword_faq("сколько зарплата", "ru")
    assert ans and ("собеседован" in ans.lower() or "hr" in ans.lower())
