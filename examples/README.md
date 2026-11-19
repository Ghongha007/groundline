# Examples

`audit_report.txt` is a **fictional** council audit, written for testing. `ai_summary.md` is a summary of it with four
planted mistakes, the kind AI summaries often make:

1. A changed number: 164 road sections completed becomes 146.
2. An overstated claim: the audit says late payments "may indicate weak controls" and found no evidence of payment for
   work not done; the summary says this "proves the council paid for work that was never done".
3. An invented quote attributed to the head of highways.
4. A sentence with no source at all (residents and a local newspaper).

```
groundline check -s examples/audit_report.txt -d examples/ai_summary.md
```

Groundline flags all four. The other four sentences match the source.
