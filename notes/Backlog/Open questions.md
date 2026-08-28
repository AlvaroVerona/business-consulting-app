# Open questions

Real gaps found during live testing, deliberately not fixed yet — either because the fix is a genuine design decision, not a quick patch, or because the next step is a comparison/experiment rather than a code change. Each has a dated entry in [CLAUDE.md](../../.claude/CLAUDE.md) with the full finding; this note tracks *what to decide*, not what happened.

## QuickAnswerService creates duplicate Findings

`answer()` calls `repo.create_finding` unconditionally for every evidence item, every call — no dedup by statement text, unlike `FinancialAnalysisService.run()` which is explicitly idempotent for this reason. Repeated questions touching the same numbers keep creating new `origin="llm"` Finding rows.

> [!question] Decision needed
> Is this actually a problem worth fixing? Each QuickAnswer's evidence arguably *should* be its own row (self-contained per answer), unlike the engine's cross-call idempotency requirement. Lean toward "leave it" unless the findings table growing unbounded becomes a real issue (e.g. for [[Decisions/LLM backend|context budget]] reasons via `_build_prior_findings_context`).

See also: [[Home]]

## Resolved

- ~~No true background monitoring~~ — closed 2026-08-24 via a launchd `LaunchAgent` (`sidecar/scripts/run_monitoring.py` + `install_monitoring.sh`/`uninstall_monitoring.sh`), runs every 6h. See the CLAUDE.md changelog entry. Not yet actually installed on Álvaro's machine — the script exists and is tested/live-verified, but `install_monitoring.sh` hasn't been run.
- ~~BusinessUnderstandingAgent hallucinated on Fermento~~ — closed 2026-08-28. Turned out not to be a model-capability limit at all: `ollama_client.py` never set `num_ctx`, so Ollama's real default (4096, confirmed via `ollama ps`) silently truncated the prompt — the full memo was likely never reaching the model. Bumped to 8192 (`OLLAMA_NUM_CTX` env override). Re-ran live: now correctly identifies Fermento as a wine bar in Malasaña. No `useClaude=true` comparison needed, no API spend required.
- ~~HypothesisManagerAgent has no document grounding~~ — closed 2026-08-28, same session as the item above (the context-window fix had to land first, or dumping full document context here would have made truncation worse, not better). Prompt now includes the BusinessProfile's operational fields, the concern's own supporting Findings, and the project's documents. Re-ran live on Fermento: hypotheses now name real specifics ("Suppliers' delays in shipping wine", actual supplier names from the wine list) instead of generic industry boilerplate. See the CLAUDE.md changelog entry for both.
