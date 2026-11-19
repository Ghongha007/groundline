"""Loading sources and splitting text into passages and sentences."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Passage:
    doc: str          # file name
    page: int | None  # page number for PDFs
    text: str
    idx: int          # position in the corpus

    @property
    def where(self) -> str:
        return f"{self.doc}, p. {self.page}" if self.page else self.doc


ABBREV = {"mr", "mrs", "ms", "dr", "prof", "st", "no", "vs", "inc", "ltd", "co", "corp", "jr", "sr", "fig", "approx",
          "e.g", "i.e", "etc", "u.s", "u.k", "rs", "govt", "dept", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
          "sept", "oct", "nov", "dec"}


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, keeping abbreviations, initials and decimals together."""
    text = re.sub(r"\s+", " ", text.replace(" ", " ")).strip()
    if not text:
        return []
    out, start = [], 0
    for m in re.finditer(r"[.!?]+[\"'”’)]*\s+(?=[\"'“‘(]?[A-Z0-9])", text):
        before = text[start:m.start()].split()
        last = before[-1].lower().rstrip(".") if before else ""
        if last in ABBREV or (len(last) == 1 and last.isalpha()):
            continue
        out.append(text[start:m.end()].strip())
        start = m.end()
    if text[start:].strip():
        out.append(text[start:].strip())
    return out


def _read_pdf(path: Path) -> list[tuple[int, str]]:
    try:
        from pypdf import PdfReader  # optional dependency
    except ImportError as e:
        raise SystemExit("Reading PDFs needs pypdf: pip install pypdf  (or convert the PDF to text first)") from e
    return [(i + 1, p.extract_text() or "") for i, p in enumerate(PdfReader(str(path)).pages)]


def _read_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</li>|</div>", "\n\n", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def load_text(path: str | Path) -> list[tuple[int | None, str]]:
    """Return [(page or None, text)] for .txt/.md/.html/.pdf files."""
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".pdf":
        return list(_read_pdf(p))
    raw = p.read_text(encoding="utf-8", errors="replace")
    if suf in (".html", ".htm"):
        raw = _read_html(raw)
    return [(None, raw)]


def passages_from(paths: list[str | Path], max_sentences: int = 3) -> list[Passage]:
    """Cut every source into short passages (paragraph pieces of up to max_sentences sentences)."""
    out: list[Passage] = []
    for path in paths:
        name = Path(path).name
        for page, txt in load_text(path):
            for para in re.split(r"\n\s*\n", txt):
                sents = split_sentences(para)
                for i in range(0, len(sents), max_sentences):
                    chunk = " ".join(sents[i:i + max_sentences]).strip()
                    if len(chunk) > 15:
                        out.append(Passage(name, page, chunk, len(out)))
    return out
