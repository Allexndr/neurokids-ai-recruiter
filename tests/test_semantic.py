from app.bot.screening import screen_language_answer
from app.bot.semantic import StepContext, interpret_answer


def test_language_svobodno_accepted():
    r = interpret_answer("свободно", StepContext.LANGUAGE)
    assert r.ok and r.value is True


def test_language_screen_no_hard_reject():
    r = screen_language_answer("не говорю по-казахски", "ru")
    assert r is None


def test_student_svoboden_not_auto_yes():
    r = interpret_answer("свободен", StepContext.STUDENT)
    assert not r.ok
