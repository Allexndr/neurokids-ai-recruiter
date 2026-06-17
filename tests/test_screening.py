from app.bot.screening import regex_parse_profile, screen_profile, wants_online


def test_no_hard_reject_profile():
    assert screen_profile({"name": "Данияр", "age": 32, "city": "other"}, "kk") is None
    assert screen_profile({"wants_online": True}, "ru") is None


def test_parse_profile_name():
    p = regex_parse_profile("Айым")
    assert p.get("name") == "Айым"


def test_parse_profile_job_search():
    p = regex_parse_profile("да, активно ищу")
    assert p.get("job_search_active") is True


def test_wants_online_detect():
    assert wants_online("онлайн жұмыс керек")
