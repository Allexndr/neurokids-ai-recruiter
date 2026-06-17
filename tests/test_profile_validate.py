from app.bot.profile_validate import (
    parse_experience_text,
    parse_job_search_answer,
    parse_name,
    parse_name_age,
    parse_student_answer,
)


def test_name_ok():
    r = parse_name("Александр")
    assert r.ok and r.data["name"] == "Александр"


def test_name_age_compat():
    r = parse_name_age("Александр")
    assert r.ok and r.data["name"] == "Александр"


def test_name_garbage():
    assert not parse_name("привет").ok
    assert not parse_name("тест").ok


def test_job_search():
    assert parse_job_search_answer("Да").ok
    assert parse_job_search_answer("2").data["job_search_active"] is False


def test_experience_text():
    r = parse_experience_text("3 года в продажах, CRM")
    assert r.ok and len(r.data["experience_summary"]) >= 8
