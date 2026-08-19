---
name: business-diagnosis
description: Diagnose a business from uploaded documents/data using strategy-consulting-inspired method (business understanding, fact base, MECE-where-it-holds, hypothesis-driven analysis). Use when asked to diagnose a company, explain a performance change, or produce a business-understanding profile for a project in this app — not for generic business advice unconnected to a specific project's evidence.
---

# Business Diagnosis

Diagnose a company the way this app's own evidence model requires: every material
statement is one of FACT, CALCULATION, INFERENCE, HYPOTHESIS, or ASSUMPTION
(`sidecar/src/schemas/evidence.py`), never bare prose. This skill is the method;
the app's `Finding` model is the contract it must produce.

## When a diagnosis is well-formed

- **Business understanding first.** Before diagnosing a problem, establish (from
  evidence, not assumption): business model, products/services, customers,
  geographies, revenue streams, cost structure, competitive position. If a
  project has no documents yet, say so and ask for them — do not diagnose an
  empty fact base.
- **Answer-first.** Lead with the conclusion, then the evidence, then the
  reasoning — mirrors the app's `QuickAnswer` shape (answer, evidence,
  reasoning, confidence, missing information, recommended next question).
- **MECE where the business supports it, not by default.** Decompose a question
  (e.g. "why did EBITDA decline?") into branches (revenue: price/volume/mix;
  costs: COGS/personnel/logistics/SG&A) only when the branches are genuinely
  independent. When they overlap or the split is forced, say so explicitly
  instead of presenting a false MECE tree.
- **Every calculation is deterministic, never eyeballed by the model.** If a
  number requires arithmetic beyond restating a source figure, mark it
  `CALCULATION` and show the formula. Do not present computed figures as
  `FACT` — a `FACT` is something a source document states directly.
- **State what's missing, don't fill the gap with confidence.** If a document
  needed to test a hypothesis wasn't uploaded, that belongs in
  `missing_information`, not folded into an inflated-confidence answer.

## Evidence typing — the actual test to apply

| Type | Test | Example |
|---|---|---|
| FACT | A source chunk states it directly; citation MUST reference a real `chunk_id`/`document_id` from the evidence context | "Revenue was $10,000 in January" (from the uploaded P&L) |
| CALCULATION | Derived by arithmetic from FACTs; `calculation` field holds the formula used | "Gross margin = (10000-6000)/10000 = 40%" |
| INFERENCE | A reasonable read of the evidence that isn't stated directly; citation may be null | "COGS growing faster than revenue is compressing margin" |
| HYPOTHESIS | A possible explanation still needing validation; pair with what would confirm/deny it | "Supplier price increases may be driving the COGS trend — needs a supplier invoice comparison" |
| ASSUMPTION | Explicitly introduced because data is unavailable; citation.chunk_id MUST be null | "Assumed no seasonal effect, since only 3 months of data were provided" |

Never invent a `chunk_id` or `document_id` that wasn't given in the evidence
context — the app's `QuickAnswerService._validate_citations` rejects these and
forces a retry; getting it right the first time keeps the answer usable.

## Confidence — coarse on purpose

Use HIGH / MEDIUM / LOW / UNKNOWN. Never a percentage — the spec's own quality
bar explicitly calls out fake precision as a failure mode (fewer than three
data points, or a single document as sole source, is not HIGH confidence).

## Scope note

This skill covers Quick Answer / diagnostic reasoning (Phase 1). Issue-tree
construction, concern/opportunity detection, and hypothesis-portfolio tracking
(status: CONFIRMED / STRONGLY SUPPORTED / PLAUSIBLE / INCONCLUSIVE / WEAK /
CONTRADICTED) are Phase 2 — see `../../DISCOVERY.md` for what's built vs.
planned, and `../../../CLAUDE_CODE_BUSINESS_CONSULTING_SPEC.md` sections 3–4
for the full framework this skill will grow into as those land.
