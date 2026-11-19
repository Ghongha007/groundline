"""HTML, Markdown and JSON reports, and a short methodology note."""
from __future__ import annotations

import html
import json
from datetime import date

from . import __version__
from .checks import Result

LABEL = {"matched": "MATCHED", "check": "CHECK", "no match": "NO MATCH", "contradicted": "CONTRADICTED"}
COLOUR = {"matched": "#2f8f4e", "check": "#c98a12", "no match": "#c2462e", "contradicted": "#8e1f8a"}


def counts(results: list[Result]) -> dict:
    c = {k: 0 for k in LABEL}
    for r in results:
        c[r.verdict] += 1
    return c


def to_json(results: list[Result], sources: list[str], draft: str) -> str:
    return json.dumps({
        "tool": f"groundline {__version__}", "draft": draft, "sources": sources, "summary": counts(results),
        "sentences": [{
            "sentence": r.sentence, "verdict": r.verdict, "coverage": r.coverage,
            "flags": [{"kind": f.kind, "text": f.text} for f in r.flags],
            "matches": [{"score": round(s, 2), "where": p.where, "text": p.text} for s, p in r.matches],
            "llm": r.llm} for r in results]}, ensure_ascii=False, indent=2)


def to_markdown(results: list[Result], sources: list[str], draft: str) -> str:
    c = counts(results)
    out = [f"# Groundline report: {draft}", "",
           f"Sources: {', '.join(sources)}  ", f"Checked {len(results)} sentences on {date.today().isoformat()}: " +
           ", ".join(f"{v} {LABEL[k].lower()}" for k, v in c.items() if v), ""]
    for i, r in enumerate(results, 1):
        out.append(f"## {i}. {LABEL[r.verdict]}")
        out.append(f"> {r.sentence}")
        out.append("")
        for f in r.flags:
            out.append(f"- **{f.kind}:** {f.text}")
        if r.matches:
            s, p = r.matches[0]
            out.append(f"- **closest passage** ({p.where}): {p.text}")
        if r.llm:
            t = "" if r.llm.get("trusted") else " (ignored)"
            out.append(f"- **AI second opinion{t}:** {r.llm.get('verdict')}. {r.llm.get('why', '')}")
        out.append("")
    out.append(methodology(sources, any(r.llm for r in results)))
    return "\n".join(out)


def methodology(sources: list[str], used_llm: bool, model: str = "") -> str:
    ai = (f"A language model{f' ({model})' if model else ''} gave a second opinion on each sentence. Its verdict was only "
          "accepted when the words it quoted actually appear in the source passage." if used_llm else
          "No AI model was used in the check.")
    return ("## Methodology note\n\n"
            f"Each sentence of the draft was compared with {len(sources)} source document(s) using Groundline "
            f"{__version__}, an open-source tool. For every sentence, the tool found the closest source passages by "
            "keyword matching and flagged numbers, direct quotes and names that do not appear in the sources, and wording "
            f"that is more certain than the source. {ai} Every flag was then reviewed by a journalist against the original "
            "documents. The tool helps find what to check; it does not decide what is true.\n")


CSS = """
:root{--bg:#f7f5ef;--card:#fff;--ink:#1d1f1e;--dim:#5d6560;--line:#e2ddd2}
@media (prefers-color-scheme:dark){:root{--bg:#121514;--card:#1b1f1d;--ink:#ecebe6;--dim:#a2aaa5;--line:#2c332f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:28px 20px 10px;max-width:1200px;margin:auto}h1{font:400 34px/1.15 Georgia,serif;margin:0 0 6px}
.meta{color:var(--dim);font-size:14px}.pills{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.pill{padding:4px 10px;border-radius:999px;color:#fff;font-size:13px;font-weight:700}
main{display:grid;grid-template-columns:1.15fr 1fr;gap:18px;max-width:1200px;margin:auto;padding:0 20px 40px}
@media (max-width:820px){main{grid-template-columns:1fr}}
.draft{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;line-height:1.9}
.s{cursor:pointer;border-bottom:3px solid;padding:1px 0;border-radius:2px}.s:hover,.s.on{background:rgba(127,127,127,.15)}
aside{position:sticky;top:12px;align-self:start;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;max-height:calc(100vh - 24px);overflow:auto}
aside h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin:14px 0 6px}
.flag{margin:6px 0;padding:8px 10px;border-left:3px solid #c98a12;background:rgba(201,138,18,.08);border-radius:4px;font-size:14.5px}
.src{margin:8px 0;padding:10px 12px;border:1px solid var(--line);border-radius:8px;font-size:14.5px}.src small{color:var(--dim);display:block;margin-bottom:4px}
.note{max-width:1200px;margin:0 auto 40px;padding:0 20px;color:var(--dim);font-size:14.5px}
mark{background:rgba(201,138,18,.35);color:inherit}
"""

JS = """
const R=JSON.parse(document.getElementById('data').textContent);const side=document.getElementById('side');
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function show(i){document.querySelectorAll('.s').forEach(e=>e.classList.toggle('on',+e.dataset.i===i));const r=R[i];
let h=`<span class="pill" style="background:${r.c}">${r.label}</span><p><b>${esc(r.sentence)}</b></p>`;
if(r.flags.length){h+='<h2>Flags</h2>'+r.flags.map(f=>`<div class="flag"><b>${f.kind}</b>: ${esc(f.text)}</div>`).join('')}
if(r.llm){h+=`<h2>AI second opinion${r.llm.trusted?'':' (ignored)'}</h2><div class="flag" style="border-color:#8e1f8a">${esc(r.llm.verdict)}. ${esc(r.llm.why||'')}${r.llm.quote?`<br><i>“${esc(r.llm.quote)}”</i>`:''}</div>`}
h+='<h2>Closest source passages</h2>'+(r.matches.length?r.matches.map(m=>{let t=esc(m.text);r.words.forEach(w=>{t=t.replace(new RegExp('\\\\b('+w+')','gi'),'<mark>$1</mark>')});return `<div class="src"><small>${esc(m.where)} · score ${m.score}</small>${t}</div>`}).join(''):'<p>None found.</p>');
side.innerHTML=h}
document.querySelectorAll('.s').forEach(e=>e.onclick=()=>show(+e.dataset.i));
const first=R.findIndex(r=>r.label!=='MATCHED');show(first<0?0:first);
"""


def to_html(results: list[Result], sources: list[str], draft: str, model: str = "") -> str:
    from .checks import tokens
    c = counts(results)
    data = []
    for r in results:
        words = sorted({w for w in tokens(r.sentence) if len(w) > 3}, key=len, reverse=True)[:12]
        data.append({"sentence": r.sentence, "label": LABEL[r.verdict], "c": COLOUR[r.verdict],
                     "flags": [{"kind": f.kind, "text": f.text} for f in r.flags],
                     "matches": [{"score": round(s, 2), "where": p.where, "text": p.text} for s, p in r.matches],
                     "words": [w for w in words if w.isalnum()], "llm": r.llm})
    spans = " ".join(f'<span class="s" data-i="{i}" style="border-color:{COLOUR[r.verdict]}">{html.escape(r.sentence)}</span>'
                     for i, r in enumerate(results))
    pills = "".join(f'<span class="pill" style="background:{COLOUR[k]}">{v} {LABEL[k].lower()}</span>'
                    for k, v in c.items() if v)
    note = methodology(sources, any(r.llm for r in results), model).replace("## Methodology note\n\n", "")
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Groundline report</title><style>{CSS}</style></head><body>
<header><h1>Groundline report</h1><div class="meta">Draft: {html.escape(draft)} &middot; Sources: {html.escape(', '.join(sources))} &middot; {date.today().isoformat()}</div>
<div class="pills">{pills}</div><div class="meta">Click any sentence to see why it was flagged and the source passages it was matched to.</div></header>
<main><div class="draft">{spans}</div><aside id="side"></aside></main>
<div class="note"><b>Methodology note.</b> {html.escape(note)}</div>
<script type="application/json" id="data">{blob}</script><script>{JS}</script></body></html>"""
