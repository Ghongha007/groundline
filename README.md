# Groundline

Check every sentence of a draft or an AI summary against the source documents it is supposed to be based on.

You give Groundline the sources (a report, a court filing, transcripts, PDFs) and the text written from them. It goes
through the draft sentence by sentence, finds the source passages each one matches, and flags what a careful editor
would ask about:

- **Numbers** that are not in the sources, with the nearest figures from the matching passage ("146" vs "164").
- **Quotes** that do not appear word for word in the sources.
- **Names** of people and organisations the sources never mention.
- **Wording that is more certain than the source**: the draft says "proves" or "confirms" where the source says "may",
  "suggests" or "alleged".
- **Sentences with no matching passage at all**, which is where invented material usually sits.

It writes a report you can click through: every sentence is coloured, and clicking one shows the flags and the source
passages side by side, with matching words highlighted. It also writes a short methodology note you can adapt for
publication or for your editor.

It works offline, needs only Python 3.10 or newer, and uploads nothing. No model is downloaded.

## What it is not

**It is not a fact-checker.** It checks the draft against *your* sources, not against the world. If a source is wrong,
a sentence that repeats it will still match.

It matches words, not meaning. A sentence that paraphrases a source heavily may be flagged even though it is fair, and a
sentence that reuses the source's words but reverses their meaning ("did not" for "did") may pass. Treat **MATCHED** as
"a passage to compare against was found", not as "true". Every flag needs a human to read the source.

## Example

Using the fictional files in [`examples/`](examples/):

```
$ groundline check -s examples/audit_report.txt -d examples/ai_summary.md

  2. CHECK: Of the 212 road sections planned, 146 were completed.
     - "146" does not appear in the sources; the closest passage has 164 and 212

  4. NO MATCH: This proves the council paid for work that was never done.
     - No passage in the sources closely matches this sentence
     - The draft says "never, proves" but the closest passage hedges ("indicate, may")

  6. CHECK: Priya Nandakumar said: "We will make the contractors pay for every failed road in the district."
     - The quotation "We will make the contractors pay for every failed road in the district." is not found word for word in the sources
     - Only part of the sentence matches the closest passage (44% of its key words)

  7. NO MATCH: Local residents have complained about potholes for years, according to the Riverford Gazette.
     - No passage in the sources closely matches this sentence
     - The name "Riverford Gazette" does not appear in the sources

8 sentences: 4 matched, 2 check, 2 no match
Report: groundline-report.html
```

## Install

```
git clone https://github.com/Ghongha007/groundline.git
cd groundline
pip install .            # or: pip install ".[pdf]" to read PDF sources
```

Or run it without installing: `python3 -m groundline check ...` from inside the folder.

```
groundline check -s report.pdf annex.pdf -d draft.md                 several sources
groundline check -s transcript.txt -d summary.txt --md notes.md      also a Markdown report
groundline check -s filing.html -d story.txt --json out.json         machine-readable output
```

Sources and drafts can be `.txt`, `.md`, `.html` or `.pdf` (text PDFs only; run OCR on scans first). The exit code is
1 when any sentence has no match or is contradicted, so it can sit in a publishing checklist or script.

## The verdicts

| Verdict | Meaning | What to do |
|---|---|---|
| **MATCHED** | A source passage covers most of the sentence's key words and nothing was flagged | Spot-check: compare the sentence with the passage shown |
| **CHECK** | A passage was found, but a number, quote, name or wording differs, or only part of the sentence matches | Read the passage and correct or source the sentence |
| **NO MATCH** | No passage closely matches | Find a source for it or cut it. This is where invented material usually is |
| **CONTRADICTED** | Only with the AI option: the model says the source contradicts the sentence, and quoted the source to show it | Read the quoted words and correct the sentence |

## Optional: an AI second opinion

Keyword matching misses meaning. If you run a local model, Groundline can ask it about each sentence too:

```
ollama pull llama3.2
groundline check -s report.txt -d draft.md --llm http://localhost:11434/v1 --model llama3.2
```

Any OpenAI-compatible API works (Ollama, LM Studio, llama.cpp server, hosted services). For a hosted API, set the key in
`GROUNDLINE_API_KEY`. Use `--only-flagged` to ask only about sentences that are already flagged, which is faster.

**The model is held to the same standard as the draft.** It must quote the source passage that decides its verdict. If
the quoted words are not in the source, its answer is marked "ignored" and does not change the verdict. A local model
keeps unpublished drafts and confidential documents on your computer; only use a hosted API for material you are
allowed to share with that provider.

## How it works

1. Sources are cut into short passages (up to three sentences, never crossing a paragraph).
2. Each draft sentence is matched to the three closest passages with BM25, the standard keyword-ranking method
   used by search engines.
3. Numbers (including "per cent", "million", "lakh" and "crore"), quotes and names in the sentence are looked up across
   all sources. Strong words ("proves", "confirms", "never", "will") are compared with hedges in the matched passage.
4. A sentence is **MATCHED** if the best passage holds at least 60% of its key words and nothing is flagged, and
   **NO MATCH** below 35%.

All of this is plain Python with no dependencies, so the results are the same on every run and every computer.

## Run the tests

```
python3 -m unittest discover -s tests -v
```

The tests run the example files and use a fake model server to check that answers with made-up quotes are ignored.

## Licence

MIT. Made by [OSINT JOURNO](https://www.osintjourno.com).
