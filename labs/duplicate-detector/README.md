# Duplicate Use Case Detector

AI portfolios fill up with the same idea wearing different names. This tool finds them.

It embeds each use case description, compares them, and groups near-duplicates. It uses a local Ollama embedding model when available (`nomic-embed-text`) and falls back to token Jaccard similarity so it always runs.

## Why

In a list of AI ideas, repetition hides as variety. Three teams propose "ask the policy," two propose "summarise the credit memo," and nobody notices until the build starts. Finding the duplicates first is the cheapest way to shrink a portfolio.

## Run

```bash
python3 duplicates.py
```

Outputs `output/duplicates.md` and `output/duplicates.html`.

Optional:

```bash
python3 duplicates.py --threshold 0.80
python3 duplicates.py --no-llm      # force the token fallback
```

## How it works

1. Load the use cases from `data/use_cases.csv`.
2. Embed each name and description (Ollama, localhost).
3. Compute cosine similarity for every pair.
4. Union-find clusters any pair above the threshold.
5. Report clusters, the top pairs, and a similarity matrix.

Default threshold is 0.78 for embeddings and 0.32 for the Jaccard fallback.

## Limitations

- Similarity is a signal, not a verdict. Read the clusters before merging anything.
- The threshold is a judgement. Lower it to catch more, raise it to catch only near-identical.
- Embeddings capture meaning, not intent. Two use cases can look similar and still serve different owners.
- The data is synthetic.
