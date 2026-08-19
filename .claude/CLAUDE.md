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
3. Found by a medium-effort code review, reproduced directly, and fixed before that commit: reportlab's `Paragraph` runs its content through a mini-XML parser (that's how our own `<b>`/`<font>` markup works), so any unescaped LLM- or user-authored text containing `<`, `>`, or `&` that looks like a tag crashed PDF generation — reproduced with a company name like "Smith & Sons". Fixed with a single `_esc()` helper (`xml.sax.saxutils.escape`) applied at every dynamic interpolation site in `pdf_report.py`.

## Phase 5 status (2026-08-19)

Scope for this phase was decided by Álvaro, not assumed: **only the two Phase 5 sub-areas with zero external dependencies** — Scenario Modeling and Continuous Monitoring. Benchmarking, web research, external market data, and M&A/due-diligence mode are explicitly deferred; the latter three need an external data source that conflicts with the standing "no paid APIs" rule (`project_ballesta4_free_llms` memory) unless Álvaro chooses one.

**Scenario Modeling** (`analysis/scenario.py`, `services/scenario_service.py`, `POST /projects/{id}/scenarios`): a what-if tool over `financial.py`'s pure functions — no LLM, no persistence (a hypothetical projection isn't evidence about the business, and persisting every interactive tweak as a Finding would flood the evidence panel). EBITDA in a scenario is always recomputed from the adjusted revenue/cogs/opex, never carried over from the baseline's reported/implied EBITDA — a stale figure would misrepresent itself as still valid under the new assumptions. SwiftUI: `ScenarioView`, a form with three percent sliders (revenue/cogs/opex) and a baseline-vs-scenario comparison.

**Continuous Monitoring** (`services/monitoring.py:record_monitoring_diff`, `MonitoringEvent` model, `GET /projects/{id}/monitoring/events`): `ConcernDetectionService` and `OpportunityDetectionService` now snapshot the previous detected set (keyed by title, since clear-and-replace gives every run's rows new ids) before clearing and recreating it, and record `new`/`resolved`/`changed` events for the diff. Shown as a timeline in `DashboardView`. No scheduling/background-job infrastructure was built — "continuous" here means "diffed on every detection run", which only happens while the sidecar is running (the app being open), not a true background daemon; that's a real scope gap if unattended monitoring while the app is closed is ever wanted.

## MVP status audit (2026-08-19)

Álvaro asked to check spec section 18's Definition of Done against actual code (not memory). Result: 9 of 13 criteria fully met. One (#6, issue trees) genuinely doesn't exist — confirmed by grep, zero code beyond a "deferred" comment. Three (#7, #8, #13 — prioritized concerns/opportunities, inspectable evidence) were **broken in the app layer despite the backend data model supporting them correctly**, fixed this pass:

- `Repository.list_concerns`/`list_opportunities` ordered by `created_at.desc()` only — no severity/confidence-based prioritization at all. Now sorted by severity rank (concerns) / confidence rank (opportunities), recency as tiebreak (`_SEVERITY_RANK`/`_CONFIDENCE_RANK` in `repository.py`).
- **The most serious one**: `DeepAnalysisView` only rendered a Concern/Opportunity if the `ExecutiveSynthesizerService`'s LLM call happened to include its id in `concern_ids`/`opportunity_ids`. A concern the deterministic engine correctly detected but the LLM's summary didn't mention was **completely invisible in the app** — a real evidence-integrity violation (a ground-truth deterministic finding silently hidden by an LLM's summarization choice), not just a missing feature. Fixed: the view now always renders every concern/opportunity/hypothesis from the project's full lists; rows the synthesis specifically referenced get a "Highlighted" badge instead of gating visibility.
- `evidence_finding_ids` on Concern/Opportunity was persisted correctly but never rendered or made clickable anywhere in the Swift app — `SidecarClient.listFindings`/`detectConcerns`/`detectOpportunities` were defined but never called from any View. Added `ProjectViewModel.findings` (loaded concurrently with everything else in `load()`) and a shared `EvidenceDisclosure`/`FindingRow` component (`Views/FindingViews.swift`, extracted from what was previously private to `ChatTurnView.swift`) used by both chat evidence and Concern/Opportunity rows.

Still genuinely missing: issue trees (#6) — not attempted this pass, deliberately deferred again pending its own focused pass (MECE decomposition of a question, with the "don't force it" escape hatch, is a real feature, not a quick add).

## Issue trees (2026-08-19) — MVP DoD is now 13/13

Built as its own focused pass, per the note above. `IssueTreeService` (LLM, `services/issue_tree_service.py`) decomposes a **user-provided** question into a tree, 2 levels deep (matches the spec's own Revenue→Price/Volume/Mix example) — deliberately NOT auto-triggered from a detected Concern's title. Spec section 2's workflow treats "define the key question" (step 3) as its own deliberate step before "build issue tree" (step 4); guessing a question from a concern title would produce a weaker tree than one the user actually means to investigate, and risks polluting Deep Analysis's automatic pipeline with a weak artifact nobody asked for.

Nodes carry `is_forced_mece`/`overlap_note` — the spec's explicit escape hatch ("do not force MECE structures where the underlying business reality does not support them; explicitly flag overlap or uncertainty," section 4). Verified live against real `llama3.1`: asked "Why did EBITDA decline this quarter?", got a correct 2-level MECE breakdown (Revenue Mix, Price Realization, Operating Expenses) *and* correctly flagged "Interest Expense" as `is_forced_mece=true` with the overlap explained ("Bundled with Operating Expenses") — the model used the escape hatch appropriately on the first attempt, not just when the retry loop forced a correction.

Persisted flat (`IssueNode.parent_id`, self-referential FK) and reassembled into nested JSON server-side (`routes.py:_issue_nodes_to_out`) — no ORM self-referential relationship, kept simple since nothing needs eager-loaded children. `POST /projects/{id}/issue-trees` (accumulates — unlike Concern/Opportunity's clear-and-replace, a project can have multiple issue trees for different questions over time, so nothing is deleted on a new one). SwiftUI: `IssueTreeView`, a question field + `OutlineGroup` rendering (needed `IssueNode.nonEmptyChildren: [IssueNode]?` since OutlineGroup treats nil, not empty array, as "leaf"). `IssueTree`/`IssueNode` needed explicit `Sendable` conformance — Swift 6's automatic synthesis didn't infer it for the self-referential-via-array struct, unlike every other flat model in this codebase.

Caught and fixed by my own tests before this ever hit a live model: `_validate_depth`'s exceeded-depth check fired even on an empty `children: []` list at depth+1, rejecting perfectly valid 2-level trees. Fixed by returning early when `nodes` is empty, before checking depth.

Fixes from a medium-effort code review before this commit:
- `ProjectViewModel.buildIssueTree()` had no re-entrancy guard — the TextField stays enabled while a build is in flight (only the Button swaps for a spinner), so a second Return press fired a duplicate POST. Added `guard !isBuildingIssueTree else { return }`.
- Depth was validated but sibling count wasn't — a model returning e.g. 20 top-level branches would've passed straight through. Added `_validate_branching` with a generous ceiling (`MAX_SIBLINGS = 8`, above the prompt's stated 2-5/4 guidance) that only catches genuinely degenerate output, not minor overshoots.
- **The serious one**: `create_issue_tree`/`create_issue_node` committed per row inside `IssueTreeService`'s recursive persist loop — a mid-tree failure left a permanently truncated tree durably saved with no way to detect or repair it. Fixed: both now `flush()` instead of `commit()` (needed so a child's `parent_id` can reference its just-created parent within the same transaction), and `IssueTreeService.run()` calls a new `Repository.commit()` once at the very end, with `Repository.rollback()` on any exception — a flushed-but-uncommitted row is still visible to queries on the same session, so skipping the final commit alone isn't sufficient; the explicit rollback is what actually discards partial work. Regression-tested by monkeypatching `create_issue_node` to fail on the 2nd node and asserting nothing at all was persisted.
- `GET /projects/{id}/issue-trees` called `list_issue_nodes` once per tree (N+1) — real given issue trees accumulate and are never cleared, unlike Concern/Opportunity. Added `Repository.list_issue_nodes_for_project` (one query, grouped by `tree_id` in the route) — O(1) queries regardless of tree count.
- The generate/parse/retry control flow was duplicated near-identically across `QuickAnswerService`, `BusinessUnderstandingAgent`, `HypothesisManagerAgent`, `ExecutiveSynthesizerService`, and now `IssueTreeService` — the same category of duplication this project already factored out once (`services/evidence_validation.py`, this same changelog, Phase 3). Extracted `llm/retry.py:generate_json_with_retry(llm, label, max_retries, build_prompt, parse)` and migrated all 5 call sites (`HypothesisManagerAgent` keeps its per-concern "return `[]` instead of raising" tolerance by catching the harness's `ValueError` at the call site, not inside the harness). Re-verified live against real `llama3.1` after the refactor: full Deep Analysis pipeline, issue tree generation, and Quick Answer all still work correctly end-to-end — not just the 131-test suite passing unchanged.

## App packaging (2026-08-19)

Until now the only way to run the macOS app was `swift run` from Terminal — no real `.app`, no icon, not launchable from Finder/Spotlight. This project deliberately isn't an Xcode project (`../DISCOVERY.md`'s architecture rationale), and there's no GUI-Xcode access in this environment to convert it into one, so app bundling had to happen via a hand-written script rather than Xcode's built-in "Archive" flow — the standard approach for indie SwiftPM-based macOS apps.

`App/Scripts/build-app.sh`: `swift build -c release`, then assembles `BusinessConsultant.app` (`Contents/MacOS`, `Contents/Resources/AppIcon.icns`, `Contents/Info.plist`) and ad-hoc code-signs it (`codesign --sign -` — local use only; real notarization needs an Apple Developer account, out of scope here). Output lands in `.build/app/` (already gitignored).

Icon: generated natively via AppKit rather than sourced from anywhere (`App/Scripts/generate_icon.swift`, run once — draws a rounded-square gradient with a white `chart.line.uptrend.xyaxis` SF Symbol at every required `.iconset` size, then `iconutil -c icns`). The generated `AppIcon.icns` is committed (`App/Resources/`); the script re-runs only if the design changes.

One real bug during this pass, caught immediately on the first run: the build script's own `echo` strings used a Unicode ellipsis character (`…`) interpolated right after `$BUNDLE_NAME` with no separating whitespace — bash's variable-name parsing in the shell's locale treated the ellipsis's raw UTF-8 continuation bytes as part of the variable name, producing `unbound variable` errors that only reproduce with that literal byte sequence. Fixed by using plain `...` (ASCII) instead — not just working around a one-off typo, but a reminder that shell scripts shouldn't interpolate non-ASCII characters directly adjacent to a variable reference regardless of terminal/editor encoding assumptions.

Verified live: `open .build/app/BusinessConsultant.app` launches the bundled app (not `swift run`) as its own process, and it talks to the sidecar exactly as before.
