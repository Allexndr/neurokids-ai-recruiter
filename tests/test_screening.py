from app.bot import content_kk as KK
from app.bot import content_ru as RU
from app.bot.screening import (
    RejectReason,
    regex_parse_profile,
    screen_profile,
    screen_schedule_answer,
    wants_online,
)


def test_reject_age_kk():
    r = screen_profile({"name": "Данияр", "age": 32, "city": "almaty"}, "kk")
    assert isinstance(r, RejectReason)
    assert r.message == KK.REJECT_AGE


def test_reject_age_ru():
    r = screen_profile({"name": "Данияр", "age": 32, "city": "almaty"}, "ru")
    assert r.message == RU.REJECT_AGE


def test_reject_city():
    r = screen_profile({"name": "Ай", "age": 25, "city": "other"}, "kk")
    assert r.message == KK.REJECT_CITY


def test_reject_online():
    r = screen_profile({"name": "Ай", "age": 25, "city": "almaty", "wants_online": True}, "ru")
    assert r.message == RU.REJECT_ONLINE


def test_reject_schedule():
    r = screen_schedule_answer("нужен график 2/2", "ru", False)
    assert isinstance(r, RejectReason)
    assert r.message == RU.REJECT_SCHEDULE


def test_parse_profile_batch():
    p = regex_parse_profile("Айым, 25-те\nЖоқ\nЖоқ")
    assert p.get("age") == 25
    assert p.get("name")


def test_wants_online_detect():
    assert wants_online("онлайн жұмыс керек")
