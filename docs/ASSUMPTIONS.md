# Assumptions and honesty notes

This project is a **demonstration of a pattern**, not a validated governance product. The following is stated plainly so nothing here is overclaimed.

## What is real

- The ontology is a real, machine-readable structure and it drives validation and gating.
- The governance gates are real logic: a high-risk use case without a named owner, a human-in-the-loop control, and a monitoring plan is held, with the reason printed.
- The scoring is deterministic, reproducible, and auditable.
- The optional LLM integration is real and runs locally through Ollama.

## What is invented

- **The data.** `data/sample_use_cases.csv` is synthetic. It is not employer data, not real policies, and not real customers.
- **The scores.** The 1 to 5 value, feasibility, and readiness values are illustrative.

## What is a judgement, not a fact

- The **weights** in the score (40, 25, 20, 15, minus effort) are a defensible starting point, not a validated model. They should be calibrated against real outcomes before anyone relies on them.
- The **buckets** (Now, Next, Later, Hold) are a convention, not a standard.
- The **risk tiers** are simplified. Real risk classification follows regulation and internal policy.

## What this is not

- It is not an AI inventory or a regulatory register.
- It is not a substitute for model risk management (for example SR 11-7, RMiT, or the EU AI Act).
- It is not a production system. There is no authentication, database, or audit trail beyond the generated report.
- The LLM rationale is unverified prose. Do not treat it as evidence.

## Why this honesty matters

A portfolio tool is only useful if the people reading it can tell what is measured, what is assumed, and what is untested. The same discipline applies to this project itself.
