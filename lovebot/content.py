"""`content/` papkasidagi matnlarni o'qish va tekshirish.

Fayllar:
  content/letters/<slug>.txt   — birinchi qator sarlavha, qolgani xat matni (HTML ruxsat)
  content/letters/<slug>.ogg   — ixtiyoriy ovozli xabar (xat bilan birga yuboriladi)
  content/reasons.txt          — har qatorda bitta sabab (oddiy matn)
  content/comfort.txt          — kayfiyat yomon bo'lganda yuboriladigan gaplar (oddiy matn)
  content/coupons.json         — kuponlar ro'yxati
  content/quiz.json            — viktorina savollari
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import CONTENT_DIR

SLUG_RE = re.compile(r"^[a-z0-9_]{1,32}$")
VOICE_SUFFIXES = (".ogg", ".oga", ".mp3", ".m4a")
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png")


def _sidecar(path: Path, suffixes: tuple[str, ...]) -> Path | None:
    """path.txt yonidagi path.jpg / path.ogg kabi faylni topadi."""
    return next((p for s in suffixes if (p := path.with_suffix(s)).exists()), None)


@dataclass(frozen=True, slots=True)
class Letter:
    slug: str
    title: str
    body: str
    voice: Path | None = None
    photo: Path | None = None


@dataclass(frozen=True, slots=True)
class Photo:
    path: Path
    caption: str = ""


@dataclass(frozen=True, slots=True)
class Coupon:
    id: str
    emoji: str
    title: str
    description: str
    limit: int  # 0 — cheksiz


@dataclass(frozen=True, slots=True)
class QuizQuestion:
    question: str
    options: tuple[str, ...]
    answer: int  # options ichidagi indeks (0 dan)
    hint: str = ""


@dataclass(frozen=True, slots=True)
class LoveMessage:
    theme: str  # fayl nomi: sevgi, dalda, birgalikda …
    text: str


@dataclass(slots=True)
class Content:
    letters: list[Letter] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    comfort: list[str] = field(default_factory=list)
    coupons: list[Coupon] = field(default_factory=list)
    quiz: list[QuizQuestion] = field(default_factory=list)
    hourly: list[LoveMessage] = field(default_factory=list)
    game: list[str] = field(default_factory=list)
    days: list[Letter] = field(default_factory=list)  # 30 kunlik kalendar, slug = "01".."30"
    gallery: list[Photo] = field(default_factory=list)
    start_photo: Path | None = None
    problems: list[str] = field(default_factory=list)

    def day(self, number: int) -> Letter | None:
        return self.days[number - 1] if 1 <= number <= len(self.days) else None

    def letter(self, slug: str) -> Letter | None:
        return next((l for l in self.letters if l.slug == slug), None)

    def coupon(self, coupon_id: str) -> Coupon | None:
        return next((c for c in self.coupons if c.id == coupon_id), None)


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def _load_letters(root: Path, problems: list[str]) -> list[Letter]:
    letters: list[Letter] = []
    if not root.exists():
        problems.append(f"{root} papkasi yo'q")
        return letters
    for path in sorted(root.glob("*.txt")):
        slug = path.stem
        if not SLUG_RE.match(slug):
            problems.append(f"letters/{path.name}: fayl nomi faqat a-z, 0-9, _ dan iborat bo'lsin")
            continue
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            problems.append(f"letters/{path.name}: bo'sh fayl")
            continue
        title, _, body = raw.partition("\n")
        body = body.strip()
        if not body:
            problems.append(f"letters/{path.name}: sarlavhadan keyin xat matni yo'q")
            continue
        letters.append(
            Letter(
                slug=slug,
                title=title.strip(),
                body=body,
                voice=_sidecar(path, VOICE_SUFFIXES),
                photo=_sidecar(path, PHOTO_SUFFIXES),
            )
        )
    if not letters:
        problems.append("letters/ ichida birorta xat yo'q")
    return letters


def _load_coupons(path: Path, problems: list[str]) -> list[Coupon]:
    if not path.exists():
        problems.append(f"{path.name} topilmadi")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        problems.append(f"{path.name}: JSON xato — {exc}")
        return []
    coupons: list[Coupon] = []
    seen: set[str] = set()
    for i, item in enumerate(data, 1):
        cid = str(item.get("id", "")).strip()
        if not SLUG_RE.match(cid):
            problems.append(f"{path.name}: #{i} id noto'g'ri ({cid!r})")
            continue
        if cid in seen:
            problems.append(f"{path.name}: id takrorlangan ({cid})")
            continue
        seen.add(cid)
        if not item.get("title"):
            problems.append(f"{path.name}: {cid} uchun title yo'q")
            continue
        coupons.append(
            Coupon(
                id=cid,
                emoji=str(item.get("emoji", "🎟")),
                title=str(item["title"]),
                description=str(item.get("description", "")),
                limit=int(item.get("limit", 1)),
            )
        )
    return coupons


def _load_quiz(path: Path, problems: list[str]) -> list[QuizQuestion]:
    if not path.exists():
        problems.append(f"{path.name} topilmadi")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        problems.append(f"{path.name}: JSON xato — {exc}")
        return []
    questions: list[QuizQuestion] = []
    for i, item in enumerate(data, 1):
        options = [str(o) for o in item.get("options", [])]
        answer = item.get("answer")
        if not item.get("question"):
            problems.append(f"{path.name}: #{i} savol matni yo'q")
            continue
        if len(options) < 2:
            problems.append(f"{path.name}: #{i} kamida 2 ta variant kerak")
            continue
        if not isinstance(answer, int) or not 0 <= answer < len(options):
            problems.append(f"{path.name}: #{i} answer 0..{len(options) - 1} oralig'ida bo'lsin")
            continue
        if any(len(o) > 60 for o in options):
            problems.append(f"{path.name}: #{i} variant 60 belgidan uzun (tugmaga sig'maydi)")
        questions.append(
            QuizQuestion(
                question=str(item["question"]),
                options=tuple(options),
                answer=answer,
                hint=str(item.get("hint", "")),
            )
        )
    return questions


def _load_hourly(root: Path, problems: list[str]) -> list[LoveMessage]:
    if not root.exists():
        problems.append("hourly/ papkasi yo'q — soatlik xabarlar yuborilmaydi")
        return []
    messages: list[LoveMessage] = []
    for path in sorted(root.glob("*.txt")):
        if not SLUG_RE.match(path.stem):
            problems.append(f"hourly/{path.name}: fayl nomi faqat a-z, 0-9, _ dan iborat bo'lsin")
            continue
        messages.extend(LoveMessage(theme=path.stem, text=line) for line in _read_lines(path))
    if not messages:
        problems.append("hourly/ ichida birorta xabar yo'q")
    return messages


def _load_days(root: Path, problems: list[str]) -> list[Letter]:
    """days/01.txt, 02.txt … — raqamlar 1 dan uzluksiz bo'lishi kerak."""
    if not root.exists():
        problems.append("days/ papkasi yo'q — kunlik kalendar ishlamaydi")
        return []
    found: dict[int, Letter] = {}
    for path in sorted(root.glob("*.txt")):
        if not path.stem.isdigit():
            problems.append(f"days/{path.name}: fayl nomi raqam bo'lsin (01.txt, 02.txt …)")
            continue
        raw = path.read_text(encoding="utf-8").strip()
        title, _, body = raw.partition("\n")
        if not raw or not body.strip():
            problems.append(f"days/{path.name}: sarlavha va matn kerak")
            continue
        found[int(path.stem)] = Letter(
            slug=path.stem,
            title=title.strip(),
            body=body.strip(),
            voice=_sidecar(path, VOICE_SUFFIXES),
            photo=_sidecar(path, PHOTO_SUFFIXES),
        )
    days: list[Letter] = []
    for n in range(1, len(found) + 1):
        if n not in found:
            problems.append(f"days/: {n}-kun fayli yo'q (raqamlar uzluksiz bo'lsin)")
            break
        days.append(found[n])
    return days


def _load_gallery(root: Path, problems: list[str]) -> list[Photo]:
    """gallery/*.jpg|png, fayl nomi bo'yicha tartiblangan. captions.txt: `fayl | so'z`."""
    if not root.exists():
        return []
    captions: dict[str, str] = {}
    for line in _read_lines(root / "captions.txt"):
        name, sep, caption = line.partition("|")
        if sep:
            captions[name.strip()] = caption.strip()
    photos = [
        Photo(path=p, caption=captions.get(p.name, ""))
        for p in sorted(root.iterdir())
        if p.suffix.lower() in PHOTO_SUFFIXES
    ]
    for name in captions:
        if not (root / name).exists():
            problems.append(f"gallery/captions.txt: {name} fayli topilmadi")
    return photos


def load_content(root: Path = CONTENT_DIR) -> Content:
    problems: list[str] = []
    content = Content(
        letters=_load_letters(root / "letters", problems),
        reasons=_read_lines(root / "reasons.txt"),
        comfort=_read_lines(root / "comfort.txt"),
        coupons=_load_coupons(root / "coupons.json", problems),
        quiz=_load_quiz(root / "quiz.json", problems),
        hourly=_load_hourly(root / "hourly", problems),
        game=_read_lines(root / "game.txt"),
        days=_load_days(root / "days", problems),
        gallery=_load_gallery(root / "gallery", problems),
        start_photo=_sidecar(root / "start.txt", PHOTO_SUFFIXES),
    )
    if not content.days:
        problems.append("days/ bo'sh — kunlik kalendar ishlamaydi")
    if not content.game:
        problems.append("game.txt bo'sh — 'Ikkalamiz' o'yini ishlamaydi")
    if not content.reasons:
        problems.append("reasons.txt bo'sh — kunlik sabablar yuborilmaydi")
    if not content.comfort:
        problems.append("comfort.txt bo'sh — kayfiyat yomon bo'lganda yuboriladigan gap yo'q")
    if not content.quiz:
        problems.append("quiz.json bo'sh — viktorina ishlamaydi")
    content.problems = problems
    return content
