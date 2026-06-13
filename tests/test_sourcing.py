import pytest

from app.sourcing.resume_parser import extract_text_from_bytes
from app.sourcing.scorer import _heuristic_score, _parse_json, parse_csv_candidates


def test_parse_json():
    assert _parse_json('{"score": 85, "summary": "ok"}')["score"] == 85


def test_heuristic_score():
    criteria = {"skills": ["python", "sql"]}
    text = "Опыт python разработки"
    r = _heuristic_score(criteria, text)
    assert r["score"] > 40
    assert "python" in r["matched_skills"]


def test_csv_import():
    data = b"name,resume\nIvan,Python dev\n"
    rows = parse_csv_candidates(data)
    assert len(rows) == 1
    assert rows[0]["name"] == "Ivan"


def test_text_extract_plain():
    assert "hello" in extract_text_from_bytes(b"hello world", "notes.txt")
