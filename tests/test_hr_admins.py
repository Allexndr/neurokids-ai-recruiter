from app.config import Settings


def test_hr_chat_ids_multiple():
    s = Settings(telegram_hr_chat_id="547331503,5450018125")
    assert s.is_hr_chat("547331503")
    assert s.is_hr_chat("5450018125")
    assert not s.is_hr_chat("999")
