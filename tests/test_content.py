import json
from pathlib import Path

from lovebot.config import CONTENT_DIR
from lovebot.content import load_content


def test_shipped_content_has_no_problems():
    content = load_content(CONTENT_DIR)
    assert content.problems == []
    assert content.letters and content.reasons and content.comfort and content.coupons and content.quiz
    assert len(content.days) == 30 and content.day(1).title == "Boshlanish" and content.day(31) is None
    assert len(content.reasons) >= 30
    assert len(content.game) >= 60 and len(content.hourly) >= 60


def test_days_must_be_contiguous(tmp_path: Path):
    days = tmp_path / "days"
    days.mkdir()
    (days / "01.txt").write_text("A\na", encoding="utf-8")
    (days / "02.txt").write_text("B\nb", encoding="utf-8")
    (days / "04.txt").write_text("D\nd", encoding="utf-8")  # 3 yo'q
    (days / "x.txt").write_text("X\nx", encoding="utf-8")
    content = load_content(tmp_path)
    assert [d.slug for d in content.days] == ["01", "02"]
    joined = "\n".join(content.problems)
    assert "3-kun fayli yo'q" in joined and "x.txt" in joined


def test_gallery_and_start_photo(tmp_path: Path):
    gallery = tmp_path / "gallery"
    gallery.mkdir()
    (gallery / "02.jpg").write_bytes(b"\x00")
    (gallery / "01.png").write_bytes(b"\x00")
    (gallery / "notes.txt").write_text("x", encoding="utf-8")
    (gallery / "captions.txt").write_text("01.png | Birinchi\n03.jpg | yo'q fayl\n", encoding="utf-8")
    (tmp_path / "start.txt").write_text("x", encoding="utf-8")
    (tmp_path / "start.png").write_bytes(b"\x00")
    content = load_content(tmp_path)
    assert [p.path.name for p in content.gallery] == ["01.png", "02.jpg"]
    assert content.gallery[0].caption == "Birinchi" and content.gallery[1].caption == ""
    assert content.start_photo is not None and content.start_photo.name == "start.png"
    assert any("03.jpg" in p for p in content.problems)


def test_letter_voice_detected(tmp_path: Path):
    letters = tmp_path / "letters"
    letters.mkdir()
    (letters / "hi.txt").write_text("Salom\nMatn", encoding="utf-8")
    (letters / "hi.ogg").write_bytes(b"\x00")
    (letters / "hi.jpg").write_bytes(b"\x00")
    (tmp_path / "reasons.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "comfort.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "coupons.json").write_text("[]", encoding="utf-8")
    (tmp_path / "quiz.json").write_text("[]", encoding="utf-8")

    content = load_content(tmp_path)
    letter = content.letter("hi")
    assert letter is not None
    assert letter.title == "Salom" and letter.body == "Matn"
    assert letter.voice is not None and letter.voice.suffix == ".ogg"
    assert letter.photo is not None and letter.photo.suffix == ".jpg"
    assert "quiz.json bo'sh" in " ".join(content.problems)


def test_invalid_entries_reported(tmp_path: Path):
    letters = tmp_path / "letters"
    letters.mkdir()
    (letters / "Bad Name.txt").write_text("T\nB", encoding="utf-8")
    (letters / "empty.txt").write_text("Faqat sarlavha", encoding="utf-8")
    (tmp_path / "coupons.json").write_text(json.dumps([{"id": "x", "title": "A"}, {"id": "x", "title": "B"}]), encoding="utf-8")
    (tmp_path / "quiz.json").write_text(json.dumps([{"question": "q", "options": ["a"], "answer": 0}]), encoding="utf-8")

    content = load_content(tmp_path)
    joined = "\n".join(content.problems)
    assert "Bad Name.txt" in joined
    assert "empty.txt" in joined
    assert "takrorlangan" in joined
    assert "kamida 2 ta variant" in joined
    assert len(content.coupons) == 1
    assert content.quiz == []
