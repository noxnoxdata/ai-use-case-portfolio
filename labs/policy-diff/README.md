# Policy Change Diff

Two versions of a policy go in. A clause-level changelog comes out.

It splits each version into clauses, matches them across versions with local embeddings, and classifies every clause as unchanged, changed, added, or removed. The output is a Markdown report and a side-by-side HTML view.

## Why

Policy changes usually arrive as a new document and a polite note. Finding what actually changed, and what it means, is manual work. This turns it into a readable diff with the changed clauses lined up next to each other.

## Run

```bash
python3 diff.py
```

Outputs `output/diff.md` and `output/diff.html`.

Optional local model explanation per change:

```bash
python3 diff.py --llm
```

## How it works

1. Load both versions, one clause per line.
2. Embed each clause (Ollama, localhost) or fall back to token Jaccard.
3. For each clause in version 2, find the most similar clause in version 1.
4. Classify: unchanged (very high similarity), changed (similar but not identical), added (no match), removed (version 1 clause with no match).
5. Emit the report and the side-by-side view.

## Limitations

- Clause matching is a signal, not a legal opinion. Read every change.
- Thresholds are a judgement and may need tuning for different documents.
- The sample policy is synthetic.
- The optional model note is unverified prose. Do not treat it as advice.
