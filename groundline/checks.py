"""Matching each draft sentence to source passages, and the deterministic checks (no AI involved)."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from .text import Passage

STOP = set("""a an the and or but if of to in on at by for with from as is are was were be been being this that these those
it its they them their he she his her we our you your i not no so than then there here which who whom whose what when where
why how all any each few more most other some such only own same too very can will just also into over under about after
before between during again further once said says say has have had do does did would should could may might must shall""".split())
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
           "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
           "hundred": 100, "half": 0.5, "dozen": 12}
MULT = {"thousand": 1e3, "k": 1e3, "million": 1e6, "mn": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "trillion": 1e12,
        "lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7}
STRONG = {"proves", "proved", "proof", "confirms", "confirmed", "certainly", "definitely", "undoubtedly", "clearly",
          "always", "never", "guaranteed", "caused", "causes", "guilty", "fact", "will"}
HEDGE = {"may", "might", "could", "suggests", "suggest", "suggested", "alleged", "allegedly", "appears", "appear",
         "likely", "possibly", "possible", "estimated", "estimate", "approximately", "around", "reportedly",
         "preliminary", "believed", "unclear", "unverified", "indicates", "indicate"}


def tokens(s: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", s.lower()):
        if w in STOP or len(w) < 2:
            continue
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


class BM25:
    def __init__(self, passages: list[Passage], k1: float = 1.4, b: float = 0.75):
        self.p = passages
        self.docs = [tokens(x.text) for x in passages]
        self.N = len(self.docs) or 1
        self.avg = sum(map(len, self.docs)) / self.N if self.docs else 1
        self.df = Counter(w for d in self.docs for w in set(d))
        self.tf = [Counter(d) for d in self.docs]
        self.k1, self.b = k1, b

    def idf(self, w: str) -> float:
        n = self.df.get(w, 0)
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def top(self, query: str, k: int = 3) -> list[tuple[float, Passage]]:
        q = tokens(query)
        scores = []
        for i, tf in enumerate(self.tf):
            L = len(self.docs[i]) or 1; s = 0.0
            for w in q:
                f = tf.get(w, 0)
                if f:
                    s += self.idf(w) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * L / self.avg))
            scores.append((s, self.p[i]))
        scores.sort(key=lambda x: -x[0])
        return [x for x in scores[:k] if x[0] > 0]


NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)(\s*%|\s*per\s?cent)?"
                    r"(?:\s*(thousand|million|billion|trillion|lakhs?|crores?|mn|bn|k|m)\b)?", re.I)


def numbers(s: str) -> list[tuple[float, str, str]]:
    """Return (value, kind, original text). kind is '%' for percentages, otherwise ''."""
    out = []
    for m in NUM_RE.finditer(s):
        raw, pct, mult = m.group(1), m.group(2), (m.group(3) or "").lower()
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        if mult in ("m",) and not re.search(r"(us\$|\$|€|£|rs|₹)\s*" + re.escape(raw), s[:m.end()].lower()):
            mult = ""                                   # "5 m" is metres unless it follows a currency sign
        v *= MULT.get(mult, 1)
        out.append((v, "%" if pct else "", m.group(0).strip()))
    for w, v in WORDNUM.items():
        for m in re.finditer(rf"\b{w}\b(\s+(thousand|million|billion|lakh|crore)s?)?", s, re.I):
            mult = (m.group(2) or "").lower()
            out.append((v * MULT.get(mult, 1), "", m.group(0)))
    return out


def same(a: float, b: float) -> bool:
    return a == b or (max(abs(a), abs(b)) > 0 and abs(a - b) / max(abs(a), abs(b)) < 0.005)


QUOTE_RE = re.compile(r"[\"“]([^\"”]{12,})[\"”]")


def norm_text(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Flag:
    kind: str      # number, quote, wording, name, match
    text: str      # plain-language explanation


@dataclass
class Result:
    sentence: str
    matches: list[tuple[float, Passage]]
    coverage: float                     # share of the sentence's content words found in the best passage
    flags: list[Flag] = field(default_factory=list)
    verdict: str = "matched"            # matched | check | no match
    llm: dict | None = None


def check_sentence(sent: str, index: BM25, corpus_norm: str, corpus_nums: list[tuple[float, str]]) -> Result:
    matches = index.top(sent, 3)
    best = matches[0][1] if matches else None
    st = set(tokens(sent))
    cov = len(st & set(tokens(best.text))) / len(st) if (st and best) else 0.0
    r = Result(sent, matches, round(cov, 2))
    # numbers
    for v, kind, raw in numbers(sent):
        if 1900 <= v <= 2100 and float(v).is_integer() and not kind:
            hay = [n for n, _ in corpus_nums]
        else:
            hay = [n for n, k in corpus_nums if k == kind or not kind]
        if not any(same(v, n) for n in hay):
            cand = [(n, x) for n, k, x in numbers(best.text) if k == kind] if best else []
            near = [x for n, x in sorted(cand, key=lambda t: abs(t[0] - v))[:2]]
            r.flags.append(Flag("number", f"\"{raw}\" does not appear in the sources" +
                                (f"; the closest passage has {' and '.join(near)}" if near else "")))
    # quotes
    for q in QUOTE_RE.findall(sent):
        if len(q.split()) >= 3 and norm_text(q) not in corpus_norm:
            r.flags.append(Flag("quote", f"The quotation “{q[:80]}” is not found word for word in the sources"))
    # stronger wording than the source
    if best:
        sw = {w for w in re.findall(r"[a-z]+", sent.lower()) if w in STRONG}
        src = set(re.findall(r"[a-z]+", best.text.lower()))
        hedges = src & HEDGE
        if sw and hedges and not (sw & src):
            r.flags.append(Flag("wording", f"The draft says “{', '.join(sorted(sw))}” but the closest passage hedges "
                                           f"(“{', '.join(sorted(hedges))}”)"))
    # proper names (two or more capitalised words in a row)
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+(?:of\s+|the\s+)?[A-Z][a-z]+)+)", sent):
        words = m.group(1).split()
        while words and words[0].lower() in STOP | STRONG:      # "The Riverford Gazette" -> "Riverford Gazette"
            words.pop(0)
        nm = " ".join(words)
        if len(words) >= 2 and norm_text(nm) not in corpus_norm:
            r.flags.append(Flag("name", f"The name “{nm}” does not appear in the sources"))
    # overall match
    if not best or cov < 0.35:
        r.verdict = "no match"
        r.flags.insert(0, Flag("match", "No passage in the sources closely matches this sentence"))
    elif r.flags or cov < 0.6:
        r.verdict = "check"
        if cov < 0.6:
            r.flags.append(Flag("match", f"Only part of the sentence matches the closest passage ({int(cov * 100)}% of its key words)"))
    return r


def check_all(draft_sentences: list[str], passages: list[Passage]) -> list[Result]:
    index = BM25(passages)
    corpus_norm = " ".join(norm_text(p.text) for p in passages)
    corpus_nums = [(v, k) for p in passages for v, k, _ in numbers(p.text)]
    return [check_sentence(s, index, corpus_norm, corpus_nums) for s in draft_sentences if len(s.split()) >= 3]
