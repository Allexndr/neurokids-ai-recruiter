import pytest

from app.bot.faq import keyword_faq


@pytest.mark.asyncio
async def test_percent_kk():
    ans = keyword_faq("Қанша %?", "kk")
    assert ans and "10" in ans and "15" in ans


def test_salary_ru():
    ans = keyword_faq("сколько зарплата", "ru")
    assert ans and "50" in ans
