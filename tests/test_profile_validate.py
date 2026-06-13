from app.bot.profile_validate import parse_experience_answer, parse_name_age, parse_student_answer


def test_name_age_ok():
    r = parse_name_age("Александр 22")
    assert r.ok and r.data["name"] == "Александр" and r.data["age"] == 22


def test_name_age_garbage():
    assert not parse_name_age("привет").ok
    assert not parse_name_age("тест").ok
    assert not parse_name_age("22").ok


def test_student_yes_no():
    assert parse_student_answer("Да").ok
    assert parse_student_answer("2").data["is_student"] is False
    assert not parse_student_answer("может быть").ok


def test_experience():
    assert parse_experience_answer("Жоқ").data["has_experience"] is False
