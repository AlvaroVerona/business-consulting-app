# Business Consulting App

AI-powered business consulting/strategy-analysis macOS app. Full spec: `../CLAUDE_CODE_BUSINESS_CONSULTING_SPEC.md`. Discovery notes, architecture rationale, and decisions log: `../DISCOVERY.md`.

## Stack

- `App/` — SwiftUI macOS app (Swift Package Manager executable, Swift 6 strict concurrency).
- `sidecar/` — Python/FastAPI backend. Owns persistence (SQLite via SQLAlchemy), document ingestion, LLM orchestration. The Swift app is a thin client over `http://127.0.0.1:8765`.

## Non-negotiable rules (spec sections 5 and 13)

1. Every conclusion is a `Finding`: FACT | CALCULATION | INFERENCE | HYPOTHESIS | ASSUMPTION (`sidecar/src/schemas/evidence.py`). Never bare prose.
2. Citations must reference a real `chunk_id`/`document_id` from that project's ingested documents — never fabricated. `QuickAnswerService._validate_citations` enforces this with a retry loop; don't weaken it.
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
