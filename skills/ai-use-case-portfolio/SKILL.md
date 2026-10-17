---
name: ai-use-case-portfolio
description: Use when triaging a portfolio of AI use cases, assessing governance readiness, or finding a shared data foundation across use cases. Applies an ontology, governance gates, deterministic scoring, and a shared-layer analysis, then returns a Now/Next/Later/Hold triage, the governance gaps, and a recommended shared data layer. Trigger phrases include "AI use case portfolio", "triage these AI ideas", "which AI use cases first", "governance gaps for AI", "shared data layer", "common data across use cases".
---

# AI Use Case Portfolio

Turn a flat list of AI ideas into a governed portfolio, then find the shared data foundation under it.

## When to use this

- Someone has a list of AI use cases and needs to know what to do first.
- A portfolio needs governance gates, not just a ranking.
- Several use cases may share data, and you need to find the common layer.
- You need a defensible, repeatable answer rather than a vibe.

## Inputs

1. **A use case list.** One row per use case. Minimum fields:
   `id, name, description, business_unit, owner, data_sources, ai_type, risk_tier, value, feasibility, data_readiness, effort_weeks, human_in_loop, monitoring, required_entities`
2. **The ontology** (or an equivalent in prose): risk tiers, governance gates, approved data sources, and a data-source-to-entity mapping.

If the user has no ontology, use the defaults in this skill and say so.

## Method (run in order)

### 1. Validate
For each use case, check the required fields are present. Flag missing owner, missing data sources, or a risk tier outside 1 to 4.

### 2. Apply governance gates before scoring
- Risk tier 3 or 4 requires a **named owner**, a **human-in-the-loop control**, and a **monitoring plan**.
- Every use case must read only **approved data sources**.
- Any gap means **Hold**, with the reason named. A high score cannot rescue a missing control.

### 3. Score (deterministic, 0 to 100)
```
score = value/5*40 + readiness/5*25 + feasibility/5*20 + (5-risk_tier)/4*15 - effort_weeks/52*10
```
Always show the breakdown so the number is explainable.

### 4. Triage
- **Now**: score at least 70, readiness at least 4, value at least 3, effort at most 12 weeks, no gaps.
- **Next**: score at least 55, no gaps.
- **Later**: everything else with no gaps.
- **Hold**: any governance gap.

### 5. Shared data layer
1. Each use case declares the entities it needs (customer, account, document, policy, and so on).
2. Count entity reuse: how many use cases need each entity.
3. A **shared entity** is used by two or more use cases.
4. Recommend a **greedy cover**: repeatedly pick the entity that covers the most uncovered use cases, until the portfolio is covered.
5. Report coverage: the share of use cases that can run on the shared layer, and which cannot.

## Output format

Return exactly these sections, in this order:

1. **Summary**: counts per bucket.
2. **Ranked portfolio**: a table with rank, use case, risk, value, readiness, effort, score, bucket.
3. **Shared data layer**: entity, number of use cases, coverage percent, then the recommended layer and overall coverage.
4. **Governance gaps**: each held use case with its named gaps.
5. **Score breakdown**: for the top few and the held few, show the factor contributions.

## Rules

- Deterministic by default. Do not let a model decide a bucket.
- Label every assumption. If the data is synthetic or self-reported, say so.
- Never invent use cases, owners, or data.
- Do not overclaim: this is a pattern, not a certified governance system.
- Keep the governance gate ahead of the score. That ordering is the whole point.

## Minimal example

Input row:
```
UC-001, Policy Q&A Assistant, ... , risk_tier=1, value=5, readiness=5, feasibility=5, effort=6, owner=Aisyah, sources=policy_repository, entities=policy;regulatory_change
```
Output: score 98.8, bucket Now, shared entities policy and regulatory_change.

Input row:
```
UC-004, Credit Memo Summarizer, ... , risk_tier=3, value=4, readiness=3, feasibility=4, effort=8, owner=TBD, monitoring=no, sources=loan_documents (unapproved)
```
Output: score 69, bucket **Hold**, gaps: no named owner, no monitoring plan, unapproved data source.
