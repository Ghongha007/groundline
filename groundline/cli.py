"""Command line: groundline check --source FILE ... --draft FILE"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import __version__
from .checks import check_all
from .report import LABEL, counts, methodology, to_html, to_json, to_markdown
from .text import load_text, passages_from, split_sentences


def draft_sentences(path: str) -> list[str]:
    out = []
    for _, txt in load_text(path):
        for para in re.split(r"\n\s*\n", txt):
            lines = [l for l in para.splitlines() if not l.lstrip().startswith(("#", "```", "|", "![", "<!--"))]
            para = re.sub(r"[*_`]+", "", " ".join(lines))            # drop markdown emphasis
            para = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", para)       # keep link text only
            out += split_sentences(para)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="groundline", description="Check every sentence of a draft or AI summary against the source documents.")
    ap.add_argument("--version", action="version", version=f"groundline {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check a draft against sources")
    c.add_argument("--source", "-s", nargs="+", required=True, help="source documents (.txt .md .html .pdf)")
    c.add_argument("--draft", "-d", required=True, help="the draft or AI summary to check")
    c.add_argument("-o", "--out", default="groundline-report.html", help="HTML report path (default: groundline-report.html)")
    c.add_argument("--md", help="also write a Markdown report to this path")
    c.add_argument("--json", help="also write a JSON report to this path")
    c.add_argument("--llm", metavar="URL", help="OpenAI-compatible API base, e.g. http://localhost:11434/v1 for Ollama")
    c.add_argument("--model", help="model name for --llm, e.g. llama3.2")
    c.add_argument("--only-flagged", action="store_true", help="ask the model only about sentences already flagged")
    c.add_argument("-q", "--quiet", action="store_true", help="print only the summary line")
    a = ap.parse_args(argv)

    for f in a.source + [a.draft]:
        if not Path(f).is_file():
            print(f"groundline: file not found: {f}", file=sys.stderr)
            return 2
    passages = passages_from(a.source)
    if not passages:
        print("groundline: no text found in the sources (scanned PDFs need OCR first)", file=sys.stderr)
        return 2
    results = check_all(draft_sentences(a.draft), passages)
    if a.llm:
        if not a.model:
            print("groundline: --llm needs --model", file=sys.stderr)
            return 2
        from .llm import second_opinion
        print(f"Asking {a.model} for a second opinion on {len(results)} sentences...", file=sys.stderr)
        second_opinion(results, a.llm, a.model, a.only_flagged)

    srcs, draft = [Path(s).name for s in a.source], Path(a.draft).name
    Path(a.out).write_text(to_html(results, srcs, draft, a.model or ""), encoding="utf-8")
    if a.md:
        Path(a.md).write_text(to_markdown(results, srcs, draft), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(to_json(results, srcs, draft), encoding="utf-8")

    if not a.quiet:
        for i, r in enumerate(results, 1):
            if r.verdict == "matched":
                continue
            print(f"\n{i:>3}. {LABEL[r.verdict]}: {r.sentence[:110]}{'...' if len(r.sentence) > 110 else ''}")
            for f in r.flags:
                print(f"     - {f.text}")
            if r.llm:
                print(f"     - AI: {r.llm['verdict']}{'' if r.llm.get('trusted') else ' (ignored)'}. {r.llm.get('why', '')}")
    cnt = counts(results)
    print(f"\n{len(results)} sentences: " + ", ".join(f"{v} {LABEL[k].lower()}" for k, v in cnt.items() if v) +
          f"\nReport: {a.out}")
    return 1 if (cnt["no match"] or cnt["contradicted"]) else 0
