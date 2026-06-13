from app.bot.screening import RejectReason, screen_language_answer
from app.bot.semantic import StepContext, interpret_answer


def test_language_svobodno_accepted():
    r = interpret_answer("свободно", StepContext.LANGUAGE)
    assert r.ok and r.value is True


def test_language_screen_not_reject_on_svobodno():
    r = screen_language_answer("свободно", "ru")
    assert r is True


def test_language_decline_still_rejects():
    r = screen_language_answer("не говорю по-казахски", "ru")
    assert isinstance(r, RejectReason)


def test_student_svoboden_not_auto_yes():
    r = interpret_answer("свободен", StepContext.STUDENT)
    assert not r.ok


def test_schedule_svoboden_as_free_text_ok_for_student_branch():
    r = interpret_answer("свободен", StepContext.STUDENT_SCHEDULE)
    assert r.ok and r.value is True
