import pytest

from app.bot.vacancy_screening import VacancyCriteria, screen_with_criteria


def test_vacancy_age_reject():
    c = VacancyCriteria(max_age=30, min_age=18)
    r = screen_with_criteria({"age": 35}, c)
    assert r is not None
    assert r.code == "age"


def test_vacancy_ok():
    c = VacancyCriteria(max_age=65, allow_remote=True)
    assert screen_with_criteria({"age": 25}, c) is None
