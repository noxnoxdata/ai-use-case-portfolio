#!/usr/bin/env python3
"""Duplicate AI Use Case Detector.

Embeds use case descriptions, compares them, and groups near-duplicates.
Uses a local Ollama embedding model when available, and falls back to token
Jaccard similarity so it always runs.

Usage:
    python3 duplicates.py
    python3 duplicates.py --threshold 0.80
    python3 duplicates.py --no-llm          # force the Jaccard fallback
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "data" / "use_cases.csv"
DEFAULT_OUT = ROOT / "output"


def load_cases(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append({
                "id": row["id"].strip(),
                "name": row["name"].strip(),
                "description": row.get("description", "").strip(),
            })
    return rows


def ollama_embed(text: str, model: str, host: str) -> list[float]:
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return data["embedding"]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def build_report(cases, sim, clusters, method, threshold) -> str:
    lines = ["# Duplicate Use Case Report\n"]
    lines.append(f"Method: {method}. Threshold: {threshold}.\n")
    lines.append(f"Use cases: {len(cases)}. Duplicate clusters: {len(clusters)}.\n")

    lines.append("## Duplicate clusters\n")
    if not clusters:
        lines.append("No near-duplicates found at this threshold.\n")
    for i, group in enumerate(clusters, 1):
        lines.append(f"### Cluster {i} ({len(group)} use cases)\n")
        for idx in group:
            c = cases[idx]
            lines.append(f"- **{c['name']}** ({c['id']}): {c['description']}")
        lines.append("")

    pairs = []
    for a in range(len(cases)):
        for b in range(a + 1, len(cases)):
            pairs.append((sim[a][b], a, b))
    pairs.sort(reverse=True)
    lines.append("## Most similar pairs\n")
    lines.append("| Use case A | Use case B | Similarity |")
    lines.append("|---|---|---|")
    for s, a, b in pairs[:10]:
        lines.append(f"| {cases[a]['name']} | {cases[b]['name']} | {s:.2f} |")
    lines.append("")
    lines.append("Similarity is a signal, not a verdict. Read the top pairs before merging anything.")
    return "\n".join(lines)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Duplicate Use Cases</title>
<style>
:root { --navy:#0F1E46; --ice:#CADCFC; --teal:#0E8A7D; --amber:#F2A900; --paper:#f7f9fc; --ink:#111827; --muted:#6b7280; }
* { box-sizing:border-box; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--paper); color:var(--ink); }
header.top { background:var(--navy); color:#fff; padding:28px 32px; }
header.top h1 { margin:0 0 6px; font-size:24px; }
header.top p { margin:0; color:var(--ice); font-size:14px; }
main { padding:24px 32px 40px; }
.grid { display:grid; grid-template-columns:1.15fr .85fr; gap:24px; align-items:start; }
.panel { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:18px 20px; }
.panel h2 { font-size:14px; text-transform:uppercase; letter-spacing:.8px; color:var(--navy); margin:0 0 12px; }
table.matrix { border-collapse:collapse; font-size:11px; }
table.matrix th, table.matrix td { border:1px solid #eef2f7; width:30px; height:30px; text-align:center; padding:0; }
table.matrix th { background:#f3f6fb; color:var(--navy); font-weight:600; }
table.matrix td { color:#334155; }
.cluster { border-left:4px solid var(--teal); background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:12px 14px; margin-bottom:12px; }
.cluster h3 { margin:0 0 6px; font-size:13px; color:var(--navy); }
.cluster li { font-size:13px; margin:3px 0; }
.muted { color:var(--muted); font-size:12px; }
.legend { display:flex; gap:12px; align-items:center; margin-top:10px; font-size:11px; color:var(--muted); }
.swatch { width:14px; height:14px; border-radius:3px; background:var(--teal); }
@media (max-width:1000px) { .grid { grid-template-columns:1fr; } }
</style>
</head>
<body>
<header class="top">
  <h1>Duplicate Use Cases</h1>
  <p>@@SUBTITLE@@</p>
</header>
<main>
  <div class="grid">
    <section class="panel">
      <h2>Similarity matrix</h2>
      <div style="overflow:auto">@@MATRIX@@</div>
      <div class="legend"><span class="swatch"></span><span>Darker means more similar. Diagonal is self-similarity.</span></div>
    </section>
    <section class="panel">
      <h2>Clusters</h2>
      @@CLUSTERS@@
    </section>
  </div>
</main>
</body>
</html>"""


def build_html(cases, sim, clusters, method, threshold) -> str:
    n = len(cases)
    head = "<tr><th></th>" + "".join(f"<th>{i+1}</th>" for i in range(n)) + "</tr>"
    body = ""
    for a in range(n):
        cells = ""
        for b in range(n):
            s = 1.0 if a == b else sim[a][b]
            alpha = max(0.06, min(0.92, s))
            cells += f"<td style='background:rgba(14,138,125,{alpha:.2f})'>{s:.2f}</td>"
        body += f"<tr><th>{a+1}</th>{cells}</tr>"
    matrix = f"<table class='matrix'>{head}{body}</table>"

    if clusters:
        cards = ""
        for i, group in enumerate(clusters, 1):
            items = "".join(f"<li><b>{cases[idx]['name']}</b> <span class='muted'>({cases[idx]['id']})</span></li>" for idx in group)
            cards += f"<div class='cluster'><h3>Cluster {i}</h3><ul style='margin:0;padding-left:18px'>{items}</ul></div>"
    else:
        cards = "<p class='muted'>No near-duplicates at this threshold.</p>"

    subtitle = f"{method} &middot; threshold {threshold} &middot; {n} use cases &middot; {len(clusters)} clusters"
    return (
        HTML_TEMPLATE.replace("@@SUBTITLE@@", subtitle)
        .replace("@@MATRIX@@", matrix)
        .replace("@@CLUSTERS@@", cards)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Find duplicate AI use cases.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--no-llm", action="store_true", help="Force the token Jaccard fallback")
    parser.add_argument("--model", default="nomic-embed-text")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    cases = load_cases(Path(args.csv))
    n = len(cases)
    method = "token Jaccard (fallback)"
    threshold = args.threshold if args.threshold is not None else 0.32
    sim = [[0.0] * n for _ in range(n)]

    if not args.no_llm:
        try:
            vectors = [
                ollama_embed(f"{c['name']}. {c['description']}", args.model, args.host.rstrip("/"))
                for c in cases
            ]
            for a in range(n):
                for b in range(n):
                    sim[a][b] = 1.0 if a == b else cosine(vectors[a], vectors[b])
            method = f"embeddings ({args.model})"
            if args.threshold is None:
                threshold = 0.78
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            print(f"Embeddings unavailable ({exc}); using token Jaccard fallback.")

    if method.startswith("token"):
        for a in range(n):
            for b in range(n):
                sim[a][b] = 1.0 if a == b else jaccard(
                    f"{cases[a]['name']}. {cases[a]['description']}",
                    f"{cases[b]['name']}. {cases[b]['description']}",
                )

    uf = UnionFind(n)
    for a in range(n):
        for b in range(a + 1, n):
            if sim[a][b] >= threshold:
                uf.union(a, b)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)
    clusters = [sorted(g) for g in groups.values() if len(g) > 1]
    clusters.sort(key=len, reverse=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "duplicates.md").write_text(build_report(cases, sim, clusters, method, threshold), encoding="utf-8")
    (out / "duplicates.html").write_text(build_html(cases, sim, clusters, method, threshold), encoding="utf-8")

    print("Duplicate Use Case Detector")
    print(f"  method: {method}")
    print(f"  threshold: {threshold}")
    print(f"  use cases: {n}")
    print(f"  clusters: {len(clusters)}")
    print(f"  wrote {out / 'duplicates.md'}")
    print(f"  wrote {out / 'duplicates.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
