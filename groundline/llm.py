"""Optional AI second opinion through any OpenAI-compatible endpoint (Ollama, LM Studio, llama.cpp, hosted APIs).

The model must quote the source word for word. If its quote is not in the passage, its verdict is discarded."""
from __future__ import annotations

import json
import os
import re
import urllib.request

from .checks import Result, norm_text

PROMPT = """You check a sentence from a news draft against source passages. Use ONLY the passages.
Answer with JSON only, no other text:
{{"verdict": "supported" | "partly" | "contradicted" | "not in sources",
  "quote": "<the exact words from a passage that decide it, copied character for character, or empty>",
  "why": "<one short sentence>"}}

SENTENCE:
{sentence}

PASSAGES:
{passages}
"""


def ask(base: str, model: str, sentence: str, passages: list[str], timeout: int = 120) -> dict:
    body = {"model": model, "temperature": 0,
            "messages": [{"role": "user", "content": PROMPT.format(
                sentence=sentence, passages="\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages)))}]}
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("GROUNDLINE_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", json.dumps(body).encode(), headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        content = json.load(r)["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return {"verdict": "error", "why": "The model did not return JSON", "quote": ""}
    try:
        out = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"verdict": "error", "why": "The model returned broken JSON", "quote": ""}
    return {k: str(out.get(k, "")) for k in ("verdict", "quote", "why")}


def second_opinion(results: list[Result], base: str, model: str, only_flagged: bool = False) -> None:
    for r in results:
        if only_flagged and r.verdict == "matched":
            continue
        texts = [p.text for _, p in r.matches]
        if not texts:
            r.llm = {"verdict": "not in sources", "quote": "", "why": "No passage to compare", "trusted": True}
            continue
        try:
            o = ask(base, model, r.sentence, texts)
        except Exception as e:  # network or server error: keep going, report it
            r.llm = {"verdict": "error", "quote": "", "why": f"{type(e).__name__}: {e}", "trusted": False}
            continue
        q = norm_text(o.get("quote", ""))
        o["trusted"] = (not q and o["verdict"] == "not in sources") or (bool(q) and any(q in norm_text(t) for t in texts))
        if not o["trusted"]:
            o["why"] = "Ignored: the model's quote is not in the sources. " + o.get("why", "")
        r.llm = o
        if o["trusted"] and o["verdict"] == "contradicted":
            r.verdict = "contradicted"
