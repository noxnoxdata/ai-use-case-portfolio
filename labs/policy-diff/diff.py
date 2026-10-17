#!/usr/bin/env python3
"""Policy Change Diff.

Compares two versions of a policy clause by clause, using local embeddings to
match clauses across versions, then classifies each as unchanged, changed,
added, or removed.

Usage:
    python3 diff.py
    python3 diff.py --llm            # add a one-line "what changed" per change
    python3 diff.py --no-llm         # force the token fallback
"""

from __future__ import annotations

import argparse
import json
import math
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_V1 = ROOT / "data" / "policy_v1.txt"
DEFAULT_V2 = ROOT / "data" / "policy_v2.txt"
DEFAULT_OUT = ROOT / "output"


def load_clauses(path: Path) -> list[str]:
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    return [ln for ln in lines if ln]


def ollama_embed(text: str, model: str, host: str) -> list[float]:
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["embedding"]


def ollama_generate(prompt: str, model: str, host: str) -> str:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return (json.load(resp).get("response") or "").strip().replace("\n", " ")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return ""


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


def similarity_matrix(v1, v2, use_llm, model, host):
    n1, n2 = len(v1), len(v2)
    if use_llm:
        try:
            e1 = [ollama_embed(c, model, host) for c in v1]
            e2 = [ollama_embed(c, model, host) for c in v2]
            return [[cosine(e1[i], e2[j]) for j in range(n2)] for i in range(n1)], True
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            print(f"Embeddings unavailable ({exc}); using token Jaccard fallback.")
    return [[jaccard(v1[i], v2[j]) for j in range(n2)] for i in range(n1)], False


def normalize(text: str) -> str:
    """Strip clause numbering and whitespace so identical text compares equal."""
    t = re.sub(r"^\s*\d+\.\s*", "", text)
    return re.sub(r"\s+", " ", t).strip().lower()


def build_diff(v1, v2, sim, embeddings):
    match_threshold = 0.62 if embeddings else 0.30

    # One-to-one greedy matching, strongest pairs first, so a clause cannot be
    # reused to match two different clauses.
    pairs = sorted(
        ((sim[i][j], i, j) for i in range(len(v1)) for j in range(len(v2))),
        reverse=True,
    )
    assigned_v1: set[int] = set()
    assigned_v2: set[int] = set()
    match: dict[int, tuple[int, float]] = {}
    for s, i, j in pairs:
        if i in assigned_v1 or j in assigned_v2:
            continue
        if s < match_threshold:
            break
        assigned_v1.add(i)
        assigned_v2.add(j)
        match[j] = (i, s)

    rows = []
    for j, clause2 in enumerate(v2):
        if j in match:
            i, s = match[j]
            status = "unchanged" if normalize(v1[i]) == normalize(clause2) else "changed"
            rows.append({"status": status, "v1": v1[i], "v2": clause2, "sim": s})
        else:
            rows.append({"status": "added", "v1": "", "v2": clause2, "sim": 0.0})

    for i, clause1 in enumerate(v1):
        if i not in assigned_v1:
            rows.append({"status": "removed", "v1": clause1, "v2": "", "sim": 0.0})

    return rows


def build_markdown(rows, method, model):
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ["added", "removed", "changed", "unchanged"]}
    lines = ["# Policy Change Diff\n"]
    lines.append(f"Method: {method}.\n")
    lines.append("## Summary\n")
    lines.append("| Status | Count |")
    lines.append("|---|---|")
    for k in ["added", "removed", "changed", "unchanged"]:
        lines.append(f"| {k.capitalize()} | {counts[k]} |")
    lines.append("")
    lines.append("## Changes\n")
    lines.append("| Status | Version 1 | Version 2 | Similarity |")
    lines.append("|---|---|---|---|")
    for r in rows:
        s = f"{r['sim']:.2f}" if r["sim"] else ""
        lines.append(f"| {r['status'].capitalize()} | {r['v1'] or '(none)'} | {r['v2'] or '(none)'} | {s} |")
    lines.append("")
    for r in rows:
        if r.get("note"):
            lines.append(f"- **{r['status'].capitalize()}**: {r['note']}")
    lines.append("")
    lines.append("Clause matching is a signal, not a legal opinion. Read every change before you rely on it.")
    return "\n".join(lines)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Policy Change Diff</title>
<style>
:root { --navy:#0F1E46; --ice:#CADCFC; --teal:#0E8A7D; --amber:#F2A900; --paper:#f7f9fc; --ink:#111827; --muted:#6b7280; --green:#2F6B3C; --red:#C0392B; }
* { box-sizing:border-box; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--paper); color:var(--ink); }
header.top { background:var(--navy); color:#fff; padding:28px 32px; }
header.top h1 { margin:0 0 6px; font-size:24px; }
header.top p { margin:0; color:var(--ice); font-size:14px; }
main { padding:24px 32px 40px; }
.summary { display:flex; gap:12px; margin-bottom:18px; flex-wrap:wrap; }
.pill { padding:6px 12px; border-radius:999px; font-size:12px; font-weight:600; background:#eef2f7; color:var(--navy); }
.row { display:grid; grid-template-columns:110px 1fr 1fr; gap:0; border:1px solid #e5e7eb; border-radius:10px; margin-bottom:10px; overflow:hidden; background:#fff; }
.status { padding:14px; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.6px; color:#fff; display:flex; align-items:center; }
.added .status { background:var(--green); }
.removed .status { background:var(--red); }
.changed .status { background:var(--amber); color:var(--navy); }
.unchanged .status { background:#94a3b8; }
.cell { padding:14px; font-size:13px; line-height:1.45; border-left:1px solid #eef2f7; }
.cell h4 { margin:0 0 4px; font-size:10px; text-transform:uppercase; letter-spacing:.6px; color:var(--muted); }
.note { grid-column:2 / -1; padding:0 14px 12px; font-size:12px; color:var(--muted); font-style:italic; }
@media (max-width:900px) { .row { grid-template-columns:1fr; } .cell { border-left:0; border-top:1px solid #eef2f7; } .note { grid-column:1; } }
</style>
</head>
<body>
<header class="top">
  <h1>Policy Change Diff</h1>
  <p>@@SUBTITLE@@</p>
</header>
<main>
  <div class="summary">@@SUMMARY@@</div>
  @@ROWS@@
</main>
</body>
</html>"""


NONE = "<span style='color:#9ca3af'>(none)</span>"


def build_html(rows, method):
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ["added", "removed", "changed", "unchanged"]}
    summary = "".join(f"<span class='pill'>{k.capitalize()}: {counts[k]}</span>" for k in ["added", "removed", "changed", "unchanged"])
    cards = ""
    for r in rows:
        note = f"<div class='note'>{r['note']}</div>" if r.get("note") else ""
        cards += (
            f"<div class='row {r['status']}'>"
            f"<div class='status'>{r['status']}</div>"
            f"<div class='cell'><h4>Version 1</h4>{r['v1'] or NONE}</div>"
            f"<div class='cell'><h4>Version 2</h4>{r['v2'] or NONE}</div>"
            f"{note}</div>"
        )
    return (
        HTML_TEMPLATE.replace("@@SUBTITLE@@", method)
        .replace("@@SUMMARY@@", summary)
        .replace("@@ROWS@@", cards)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff two versions of a policy.")
    parser.add_argument("--v1", default=str(DEFAULT_V1))
    parser.add_argument("--v2", default=str(DEFAULT_V2))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--llm", action="store_true", help="Add a one-line explanation per change")
    parser.add_argument("--no-llm", action="store_true", help="Force the token fallback")
    parser.add_argument("--model", default="nomic-embed-text")
    parser.add_argument("--gen-model", default="qwen2.5:7b")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    v1 = load_clauses(Path(args.v1))
    v2 = load_clauses(Path(args.v2))
    host = args.host.rstrip("/")

    use_embeddings = not args.no_llm
    sim, embeddings = similarity_matrix(v1, v2, use_embeddings, args.model, host)
    rows = build_diff(v1, v2, sim, embeddings)

    method = f"embeddings ({args.model})" if embeddings else "token Jaccard (fallback)"

    if args.llm:
        for r in rows:
            if r["status"] in {"changed", "added"}:
                prompt = (
                    "In one plain sentence, state what changed and why it matters. "
                    f"Version 1: {r['v1'] or '(nothing)'}\nVersion 2: {r['v2']}\n"
                    "Be factual. Do not invent."
                )
                note = ollama_generate(prompt, args.gen_model, host)
                if note:
                    r["note"] = note

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "diff.md").write_text(build_markdown(rows, method, args.gen_model), encoding="utf-8")
    (out / "diff.html").write_text(build_html(rows, method), encoding="utf-8")

    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ["added", "removed", "changed", "unchanged"]}
    print("Policy Change Diff")
    print(f"  method: {method}")
    for k in ["added", "removed", "changed", "unchanged"]:
        print(f"  {k}: {counts[k]}")
    print(f"  wrote {out / 'diff.md'}")
    print(f"  wrote {out / 'diff.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
