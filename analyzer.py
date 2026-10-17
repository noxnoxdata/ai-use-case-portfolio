#!/usr/bin/env python3
"""
AI Use Case Portfolio Analyzer
==============================

A small, dependency-free tool that applies a lightweight ontology and governance
gates to a portfolio of AI use cases, then triages them into Now / Next / Later / Hold
and finds the shared data foundation across them.

The point is not the scoring formula. The point is the pattern: a shared ontology
plus explicit governance gates plus entity reuse turns a flat list of ideas into a
governed portfolio built on one foundation.

Usage:
    python3 analyzer.py                 # generate the report from the sample data
    python3 analyzer.py --llm           # also ask a local Ollama model for a rationale
    python3 analyzer.py --csv path.csv  # use another CSV
    python3 analyzer.py --out output    # write to another directory

No third-party dependencies. Python 3.9+.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_ONTOLOGY = ROOT / "ontology" / "use_case_ontology.json"
DEFAULT_CSV = ROOT / "data" / "sample_use_cases.csv"
DEFAULT_OUT = ROOT / "output"
BUCKETS = ["Now", "Next", "Later", "Hold"]


# --------------------------------------------------------------------------- #
# Ontology and data loading
# --------------------------------------------------------------------------- #

def load_ontology(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "y", "true", "1"}


@dataclass
class UseCase:
    id: str
    name: str
    description: str
    business_unit: str
    owner: str
    data_sources: list[str]
    ai_type: str
    risk_tier: int
    value: float
    feasibility: float
    data_readiness: float
    effort_weeks: float
    human_in_loop: bool
    monitoring: bool
    required_entities: list[str] = field(default_factory=list)
    score: float = 0.0
    bucket: str = ""
    flags: list[str] = field(default_factory=list)
    rationale: str = ""

    @property
    def has_named_owner(self) -> bool:
        return bool(self.owner) and self.owner.strip().upper() not in {"TBD", "NONE", "UNASSIGNED", ""}

    def governance_gaps(self, approved_sources: set[str]) -> list[str]:
        """Apply the governance gates from the ontology. Gaps force a Hold."""
        gaps: list[str] = []
        if self.risk_tier >= 3:
            if not self.has_named_owner:
                gaps.append("no named business owner")
            if not self.human_in_loop:
                gaps.append("no human-in-the-loop control")
            if not self.monitoring:
                gaps.append("no monitoring plan")
        unknown = [s for s in self.data_sources if s not in approved_sources]
        if unknown:
            gaps.append("unapproved data source: " + ", ".join(unknown))
        return gaps


def score_breakdown(uc: UseCase) -> dict[str, float]:
    """The points each factor contributes. Transparent by design."""
    value = max(0.0, min(uc.value, 5.0)) / 5.0 * 40.0
    readiness = max(0.0, min(uc.data_readiness, 5.0)) / 5.0 * 25.0
    feasibility = max(0.0, min(uc.feasibility, 5.0)) / 5.0 * 20.0
    risk_tier = max(1, min(uc.risk_tier, 4))
    risk = (5 - risk_tier) / 4.0 * 15.0
    effort = -min(max(uc.effort_weeks, 0.0), 52.0) / 52.0 * 10.0
    return {
        "value": round(value, 1),
        "readiness": round(readiness, 1),
        "feasibility": round(feasibility, 1),
        "risk": round(risk, 1),
        "effort": round(effort, 1),
    }


def compute_score(uc: UseCase) -> float:
    """Weighted 0-100 priority score. Higher is better."""
    raw = sum(score_breakdown(uc).values())
    return round(max(0.0, min(raw, 100.0)), 1)


def assign_bucket(uc: UseCase) -> str:
    if uc.flags:
        return "Hold"
    if uc.score >= 70 and uc.data_readiness >= 4 and uc.effort_weeks <= 12 and uc.value >= 3:
        return "Now"
    if uc.score >= 55:
        return "Next"
    return "Later"


def load_use_cases(
    path: Path,
    approved_sources: set[str],
    source_entities: dict[str, list[str]] | None = None,
) -> list[UseCase]:
    source_entities = source_entities or {}
    cases: list[UseCase] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            data_sources = [s.strip() for s in row.get("data_sources", "").split(";") if s.strip()]
            explicit = [e.strip() for e in row.get("required_entities", "").split(";") if e.strip()]
            if explicit:
                required = explicit
            else:
                derived: list[str] = []
                for source in data_sources:
                    for entity in source_entities.get(source, []):
                        if entity not in derived:
                            derived.append(entity)
                required = derived
            uc = UseCase(
                id=row.get("id", "").strip(),
                name=row.get("name", "").strip(),
                description=row.get("description", "").strip(),
                business_unit=row.get("business_unit", "").strip(),
                owner=row.get("owner", "").strip(),
                data_sources=data_sources,
                ai_type=row.get("ai_type", "").strip(),
                risk_tier=int(parse_float(row.get("risk_tier", "1"), 1)),
                value=parse_float(row.get("value", "0")),
                feasibility=parse_float(row.get("feasibility", "0")),
                data_readiness=parse_float(row.get("data_readiness", "0")),
                effort_weeks=parse_float(row.get("effort_weeks", "0")),
                human_in_loop=parse_bool(row.get("human_in_loop", "")),
                monitoring=parse_bool(row.get("monitoring", "")),
                required_entities=required,
            )
            uc.flags = uc.governance_gaps(approved_sources)
            uc.score = compute_score(uc)
            uc.bucket = assign_bucket(uc)
            cases.append(uc)
    cases.sort(key=lambda c: c.score, reverse=True)
    return cases


def shared_layer_analysis(cases: list[UseCase], ontology: dict[str, Any]) -> dict[str, Any]:
    """Find entities reused across use cases and recommend a shared data foundation.

    Two views: entity reuse (what is common) and a greedy cover (the smallest set
    of entities that reaches the most use cases).
    """
    entity_to_cases: dict[str, set[str]] = defaultdict(set)
    for c in cases:
        for entity in c.required_entities:
            entity_to_cases[entity].add(c.id)

    total = len(cases)
    ranked = sorted(entity_to_cases.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    uncovered = {c.id for c in cases}
    chosen: list[dict[str, Any]] = []
    while uncovered:
        best_entity: str | None = None
        best_gain: set[str] = set()
        for entity, ids in entity_to_cases.items():
            gain = ids & uncovered
            if len(gain) > len(best_gain):
                best_entity, best_gain = entity, gain
        if best_entity is None or not best_gain:
            break
        chosen.append({
            "entity": best_entity,
            "adds": len(best_gain),
            "total": len(entity_to_cases[best_entity]),
        })
        uncovered -= best_gain

    coverage = (total - len(uncovered)) / total * 100.0 if total else 0.0
    return {
        "entity_to_cases": entity_to_cases,
        "ranked": ranked,
        "chosen": chosen,
        "uncovered": sorted(uncovered),
        "coverage": round(coverage, 1),
        "total": total,
    }


# --------------------------------------------------------------------------- #
# Optional local LLM rationale (Ollama, localhost only)
# --------------------------------------------------------------------------- #

def llm_rationale(uc: UseCase, model: str, host: str) -> str:
    prompt = (
        "You are an AI governance analyst. In at most two sentences, explain why the "
        f"use case '{uc.name}' landed in the '{uc.bucket}' bucket (priority score {uc.score}/100, "
        f"risk tier {uc.risk_tier}/4), and name one thing to watch. Be plain and factual. "
        "Do not invent facts."
    )
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        text = (data.get("response") or "").strip().replace("\n", " ")
        return text
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        return f"(local model unavailable: {exc})"


# --------------------------------------------------------------------------- #
# Output: markdown report and a single-file HTML dashboard
# --------------------------------------------------------------------------- #

def build_markdown(cases: list[UseCase], ontology: dict[str, Any], llm_used: bool) -> str:
    lines: list[str] = []
    lines.append("# AI Use Case Portfolio Report\n")
    lines.append(
        f"Generated by the AI Use Case Portfolio Analyzer. "
        f"Ontology: {ontology['name']} v{ontology['version']}.\n"
    )

    counts = {b: sum(1 for c in cases if c.bucket == b) for b in BUCKETS}
    lines.append("## Summary\n")
    lines.append("| Bucket | Count |")
    lines.append("|---|---|")
    for b in BUCKETS:
        lines.append(f"| {b} | {counts[b]} |")
    lines.append("")

    lines.append("## Ranked portfolio\n")
    lines.append("| Rank | Use case | AI type | Risk | Value | Readiness | Effort (wk) | Score | Bucket |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for i, c in enumerate(cases, 1):
        lines.append(
            f"| {i} | {c.name} | {c.ai_type} | {c.risk_tier} | {c.value:g} | "
            f"{c.data_readiness:g} | {c.effort_weeks:g} | {c.score} | {c.bucket} |"
        )
    lines.append("")

    shared = shared_layer_analysis(cases, ontology)
    lines.append("## Shared data layer\n")
    lines.append(
        f"Entity reuse across {shared['total']} use cases. A shared entity is needed by "
        "two or more use cases.\n"
    )
    lines.append("| Entity | Use cases | Coverage |")
    lines.append("|---|---|---|")
    for entity, ids in shared["ranked"]:
        pct = round(len(ids) / shared["total"] * 100) if shared["total"] else 0
        lines.append(f"| {entity} | {len(ids)} | {pct}% |")
    lines.append("")
    lines.append("**Recommended shared layer (greedy cover):**\n")
    for item in shared["chosen"]:
        lines.append(
            f"- {item['entity']} (adds {item['adds']} use cases, used by {item['total']} in total)"
        )
    lines.append("")
    lines.append(f"**Coverage:** {shared['coverage']}% of use cases can run on this shared layer.")
    if shared["uncovered"]:
        lines.append(f"**Not covered:** {', '.join(shared['uncovered'])}")
    lines.append("")

    gaps = [c for c in cases if c.flags]
    if gaps:
        lines.append("## Governance gaps (held)\n")
        for c in gaps:
            lines.append(f"- **{c.name}** ({c.bucket}): " + "; ".join(c.flags))
        lines.append("")

    for b in BUCKETS:
        items = [c for c in cases if c.bucket == b]
        if not items:
            continue
        lines.append(f"## {b}\n")
        for c in items:
            bd = score_breakdown(c)
            lines.append(f"### {c.name}\n")
            lines.append(f"- Business unit: {c.business_unit}")
            lines.append(f"- Owner: {c.owner}")
            lines.append(f"- AI type: {c.ai_type}")
            lines.append(f"- Risk tier: {c.risk_tier}/4")
            lines.append(f"- Data sources: {', '.join(c.data_sources) or 'none'}")
            lines.append(f"- Required entities: {', '.join(c.required_entities) or 'none'}")
            lines.append(f"- Score: {c.score}/100")
            lines.append(
                f"- Score breakdown: value {bd['value']}, readiness {bd['readiness']}, "
                f"feasibility {bd['feasibility']}, risk {bd['risk']}, effort {bd['effort']}"
            )
            if c.flags:
                lines.append(f"- Governance gaps: {'; '.join(c.flags)}")
            if llm_used and c.rationale:
                lines.append(f"- Rationale: {c.rationale}")
            lines.append("")
    return "\n".join(lines)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Use Case Portfolio</title>
<style>
:root { --navy:#0F1E46; --ice:#CADCFC; --amber:#F2A900; --teal:#0E8A7D; --paper:#f7f9fc; --ink:#111827; --muted:#6b7280; }
* { box-sizing:border-box; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--paper); color:var(--ink); }
header.top { background:var(--navy); color:#fff; padding:28px 32px; }
header.top h1 { margin:0 0 6px; font-size:24px; letter-spacing:.2px; }
header.top p { margin:0; color:var(--ice); font-size:14px; }
.shared { margin:24px 32px 0; background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:18px 20px; }
.shared h2 { font-size:15px; text-transform:uppercase; letter-spacing:.8px; color:var(--navy); margin:0 0 4px; }
.shared .lead { font-size:13px; color:var(--muted); margin:0 0 12px; }
.ents { display:grid; grid-template-columns:repeat(2,1fr); gap:8px 28px; }
.ent { display:grid; grid-template-columns:130px 1fr 32px; align-items:center; gap:10px; font-size:12.5px; }
.ent .bar { background:#eef2f7; border-radius:999px; height:8px; overflow:hidden; }
.ent .bar i { display:block; height:100%; background:var(--teal); }
.ent b { color:var(--navy); text-align:right; }
.cover { font-size:12.5px; color:#374151; margin:12px 0 0; }
.board { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; padding:24px 32px 40px; align-items:start; }
.col header { display:flex; justify-content:space-between; align-items:baseline; margin:0 0 10px; }
.col h2 { font-size:15px; text-transform:uppercase; letter-spacing:.8px; color:var(--navy); margin:0; }
.count { background:var(--navy); color:#fff; border-radius:999px; padding:2px 9px; font-size:12px; }
.card { background:#fff; border:1px solid #e5e7eb; border-left:4px solid var(--teal); border-radius:10px; padding:14px; margin-bottom:12px; box-shadow:0 1px 2px rgba(16,24,40,.04); }
.card-top { display:flex; justify-content:space-between; align-items:center; }
.pill { font-size:11px; font-weight:600; padding:2px 8px; border-radius:999px; background:#eef2f7; color:var(--navy); }
.risk-3 { background:#fef3c7; color:#92400e; }
.risk-4 { background:#fee2e2; color:#991b1b; }
.score { font-weight:700; color:var(--navy); }
.card h3 { font-size:14px; margin:8px 0 4px; }
.meta { font-size:12px; color:var(--muted); margin:0 0 6px; }
.desc { font-size:12.5px; color:#374151; margin:0 0 6px; }
.breakdown { font-size:11.5px; color:var(--muted); margin:4px 0 0; }
.gaps { font-size:12px; color:#991b1b; background:#fef2f2; border-radius:6px; padding:6px 8px; margin:6px 0 0; }
.rationale { font-size:12px; color:#374151; font-style:italic; margin:6px 0 0; }
.empty { color:var(--muted); font-size:13px; }
footer { padding:0 32px 32px; color:var(--muted); font-size:12px; }
@media (max-width:1100px) { .board { grid-template-columns:repeat(2,1fr); } .ents { grid-template-columns:1fr; } }
@media (max-width:640px) { .board { grid-template-columns:1fr; } }
</style>
</head>
<body>
<header class="top">
  <h1>AI Use Case Portfolio</h1>
  <p>@@SUBTITLE@@</p>
</header>
@@SHARED@@
<div class="board">
@@COLUMNS@@
</div>
<footer>Generated by the AI Use Case Portfolio Analyzer. Synthetic data. Scoring is a model, not a verdict.</footer>
</body>
</html>"""


def build_html(cases: list[UseCase], ontology: dict[str, Any], llm_used: bool) -> str:
    counts = {b: sum(1 for c in cases if c.bucket == b) for b in BUCKETS}
    shared = shared_layer_analysis(cases, ontology)

    ent_rows = ""
    for entity, ids in shared["ranked"][:8]:
        pct = round(len(ids) / shared["total"] * 100) if shared["total"] else 0
        ent_rows += (
            f"<div class='ent'><span>{entity}</span>"
            f"<span class='bar'><i style='width:{pct}%'></i></span>"
            f"<b>{len(ids)}</b></div>"
        )
    chosen = ", ".join(item["entity"] for item in shared["chosen"])
    shared_html = (
        f"<section class='shared'><h2>Shared data layer</h2>"
        f"<p class='lead'>{shared['coverage']}% of use cases can run on one shared foundation.</p>"
        f"<div class='ents'>{ent_rows}</div>"
        f"<p class='cover'>Recommended layer: {chosen}</p></section>"
    )

    def card(c: UseCase) -> str:
        gap = ""
        if c.flags:
            gap = f"<p class='gaps'>Gaps: {'; '.join(c.flags)}</p>"
        rationale = ""
        if llm_used and c.rationale:
            rationale = f"<p class='rationale'>{c.rationale}</p>"
        bd = score_breakdown(c)
        breakdown = (
            f"<p class='breakdown'>value {bd['value']} &middot; readiness {bd['readiness']} "
            f"&middot; feasibility {bd['feasibility']} &middot; risk {bd['risk']} "
            f"&middot; effort {bd['effort']}</p>"
        )
        return (
            f"<article class='card'>"
            f"<div class='card-top'>"
            f"<span class='pill risk-{c.risk_tier}'>Risk {c.risk_tier}</span>"
            f"<span class='score'>{c.score}</span>"
            f"</div>"
            f"<h3>{c.name}</h3>"
            f"<p class='meta'>{c.business_unit} &middot; {c.ai_type}</p>"
            f"<p class='desc'>{c.description}</p>"
            f"{breakdown}{gap}{rationale}"
            f"</article>"
        )

    columns = ""
    for b in BUCKETS:
        items = [c for c in cases if c.bucket == b]
        cards = "".join(card(c) for c in items) or "<p class='empty'>None</p>"
        columns += (
            f"<section class='col'><header><h2>{b}</h2>"
            f"<span class='count'>{counts[b]}</span></header>{cards}</section>"
        )

    subtitle = f"{ontology['name']} v{ontology['version']} &middot; triaged into Now / Next / Later / Hold"
    return (
        HTML_TEMPLATE.replace("@@SHARED@@", shared_html)
        .replace("@@COLUMNS@@", columns)
        .replace("@@SUBTITLE@@", subtitle)
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Triage an AI use case portfolio.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--ontology", default=str(DEFAULT_ONTOLOGY))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--llm", action="store_true", help="Ask a local Ollama model for a rationale per use case")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"))
    parser.add_argument("--host", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    args = parser.parse_args(argv)

    ontology = load_ontology(Path(args.ontology))
    approved = set(ontology.get("approved_data_sources", []))
    source_entities = ontology.get("data_source_entities", {})
    cases = load_use_cases(Path(args.csv), approved, source_entities)

    if args.llm:
        for c in cases:
            c.rationale = llm_rationale(c, args.model, args.host.rstrip("/"))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "portfolio-report.md").write_text(build_markdown(cases, ontology, args.llm), encoding="utf-8")
    (out / "portfolio.html").write_text(build_html(cases, ontology, args.llm), encoding="utf-8")

    counts = {b: sum(1 for c in cases if c.bucket == b) for b in BUCKETS}
    shared = shared_layer_analysis(cases, ontology)
    print("AI Use Case Portfolio Analyzer")
    print(f"  use cases: {len(cases)}")
    for b in BUCKETS:
        print(f"  {b}: {counts[b]}")
    print(f"  shared layer coverage: {shared['coverage']}%")
    print(f"  wrote {out / 'portfolio-report.md'}")
    print(f"  wrote {out / 'portfolio.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
