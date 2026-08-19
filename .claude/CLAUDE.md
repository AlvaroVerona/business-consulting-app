# Business Consulting App

AI-powered business consulting/strategy-analysis macOS app. Full spec: `../CLAUDE_CODE_BUSINESS_CONSULTING_SPEC.md`. Discovery notes, architecture rationale, and decisions log: `../DISCOVERY.md`.

## Stack

- `App/` — SwiftUI macOS app (Swift Package Manager executable, Swift 6 strict concurrency).
- `sidecar/` — Python/FastAPI backend. Owns persistence (SQLite via SQLAlchemy), document ingestion, LLM orchestration. The Swift app is a thin client over `http://127.0.0.1:8765`.

## Non-negotiable rules (spec sections 5 and 13)

1. Every conclusion is a `Finding`: FACT | CALCULATION | INFERENCE | HYPOTHESIS | ASSUMPTION (`sidecar/src/schemas/evidence.py`). Never bare prose.
2. Citations must reference a real `chunk_id`/`document_id` from that project's ingested documents — never fabricated. `services/evidence_validation.py:validate_evidence_citations` enforces this with a retry loop (used by every LLM-evidence-producing service: QuickAnswerService, BusinessUnderstandingAgent, ...); don't weaken it.
3. Arithmetic belongs in Python, not in an LLM's head. **A local smoke test on 2026-08-19 caught llama3.1 making a real arithmetic error** (computed a gross-margin percentage off by ~3.5% relative) inside a `CALCULATION`-typed finding it otherwise formatted correctly. The JSON contract and citation validation worked; the arithmetic didn't. Phase 2 built `sidecar/src/analysis/financial.py` + `period_extractor.py` (deterministic, no LLM) to fix this — verified live: with the engine's numbers injected into Quick Answer's prompt as "ALREADY-COMPUTED FINDINGS", llama3.1 correctly reused the exact deterministic values instead of recomputing. That same smoke test also caught a second, subtler bug: the first prompt format listed each engine finding as `finding_id=9 chunk_id=1 ...`, and the model sometimes cited the `finding_id` as if it were `citation.chunk_id`. Fixed by dropping `finding_id` from the prompt entirely (see `_build_prior_findings_context` in `quick_answer_service.py`) — a `Finding.origin` column ("engine" vs "llm") is what makes the entries in this prompt section trustworthy.
4. LLM backend is hybrid: local Ollama (`llama3.1`) by default, Claude API only on a caller's explicit per-call opt-in (`sidecar/src/llm/router.py`). Never make Claude the silent default.

## Running it

```bash
cd sidecar && uv sync --extra dev && uv run uvicorn src.main:app --reload --port 8765
cd App && swift run
```

Tests: `cd sidecar && uv run pytest`.

## Skills

`.claude/skills/business-diagnosis/SKILL.md` — evidence-typing method for diagnostic reasoning. More skills land as further Phase 2/3 features are built — see spec section 9 for the full planned tree.

## Phase 2 status (2026-08-19)

Built: deterministic financial engine (`analysis/financial.py`, `period_extractor.py`, `financial_analysis_service.py`) computing gross margin, EBITDA margin (implied when not reported), opex ratio, and cross-period trends from ingested CSV/XLSX rows via column-name heuristics (no LLM). Rule-based `ConcernDetectionService` (margin compression, revenue decline) and `OpportunityDetectionService` (opex efficiency improvement) run on top of it — deterministic, not LLM judgment. `Hypothesis` model + CRUD (status: CONFIRMED/STRONGLY_SUPPORTED/PLAUSIBLE/INCONCLUSIVE/WEAK/CONTRADICTED) — tracking only, no auto-generation yet.

Deliberately deferred to Phase 3 (ties into Deep Analysis mode's orchestration, spec section 15): issue trees, hypothesis auto-generation, and broader opportunity detection (cross-sell, pricing, market white-space) — those need data this app doesn't ingest yet (customer-level, market data).

`FinancialAnalysisService.run()` is idempotent by statement text (a Finding's statement embeds its computed value, e.g. "Gross margin in Jan was 60.0%.") — re-running it, including indirectly via both `/concerns/detect` and `/opportunities/detect` calling it independently, reuses existing rows instead of creating duplicates. Only genuinely new/changed numbers create new Finding rows.

## Phase 3 status (2026-08-19)

Built the full Deep Analysis pipeline (`services/deep_analysis_orchestrator.py`, spec section 2/15): `BusinessUnderstandingAgent` (LLM, same evidence-citation contract as Quick Answer) → `FinancialAnalysisService` → `ConcernDetectionService`/`OpportunityDetectionService` → `HypothesisManagerAgent` (LLM, one root-cause-hypothesis batch per concern, **forces every generated hypothesis to status=PLAUSIBLE regardless of what the LLM proposes** — an untested hypothesis cannot self-assign CONFIRMED) → `QualityReviewerService` (deterministic: flags unsupported claims, double counting, unevidenced hypothesis statuses) → `ExecutiveSynthesizerService` (LLM, spec section 11's format, `concern_ids`/`opportunity_ids` validated against what's real for the project). Persisted as `DeepAnalysisRun` (status RUNNING/COMPLETED/FAILED).

BusinessUnderstandingAgent's failure degrades the run (continues with `business_profile=None`) rather than aborting it — the deterministic steps below don't depend on it. ExecutiveSynthesizerService's failure does mark the whole run FAILED, since without it there's no useful output.

Verified live end-to-end against local `llama3.1` (a wine-bar memo + a 3-month declining-margin P&L): correct business profile extracted from the narrative memo, correct concern/hypothesis/synthesis linkage, all citations valid, zero quality issues flagged, ~50s total for the full 3-LLM-call pipeline (business understanding → hypotheses → synthesis) — no retries needed on this run, though the retry paths are unit-tested since local-model reliability is not guaranteed run to run (see the Phase 1/2 arithmetic and citation-conflation bugs above).

Deliberately deferred (see spec section 15 phasing): issue-tree construction (MECE decomposition — genuinely needs its own focused pass, not a stub), true parallel multi-agent execution (current pipeline is sequential, matching `agent-platform`'s proven pattern), and a qualitative LLM-based pass in QualityReviewerService (current version is deterministic/mechanical checks only).

Shared helper extracted this phase: `services/evidence_validation.py:validate_evidence_citations` — QuickAnswerService and BusinessUnderstandingAgent both had near-identical citation-validation logic; factored out before it could drift.

## Phase 4 status (2026-08-19)

Built professional outputs (spec section 15 Phase 4) as a pure rendering layer over already-validated data — **no LLM calls happen while building or rendering a report**. `reports/report_context.py:build_report_context` assembles a `ReportContext` (company, project, latest COMPLETED `DeepAnalysisRun`'s synthesis if any, business profile, financial analysis, concerns, opportunities, hypotheses); `reports/pdf_report.py` (reportlab), `reports/pptx_report.py` (python-pptx), `reports/excel_export.py` (openpyxl, already a dependency) each render it. All three degrade gracefully when no Deep Analysis run has completed yet — they show what's available rather than blocking the export. Every PDF/PPTX carries the spec section 1 disclaimer ("not affiliated with... McKinsey, BCG, Bain...").

SwiftUI additions: an Export menu (PDF/PowerPoint/Excel, `NSSavePanel`) in `DeepAnalysisView`, and a new `DashboardView` (Swift Charts) showing revenue/margin trend lines plus concern/opportunity/hypothesis counts — reads `/projects/{id}/analysis/financial` directly, so it's the same deterministic numbers as everywhere else, not a separate computation.

Two real bugs caught by generating an actual PDF from live Deep Analysis output (not just unit tests) and reading it:
1. The 90-Day Action Plan and Business Performance tables used plain strings as reportlab `Table` cell content, which does not reliably word-wrap within a fixed column width — long LLM-authored text visibly overlapped adjacent cells. Fixed by wrapping cell content in `Paragraph` flowables, which do wrap. Regression-tested by asserting the cells are `Paragraph` instances, since text-extraction-based PDF tests can't detect visual overlap.
2. A Strategic Option's `recommendation` field (required `str`, not `Optional`) came back as `""` from the LLM, rendering a blank line that reads as a bug even though it isn't one. Added an `_or_not_stated()` fallback for that field's siblings too.
