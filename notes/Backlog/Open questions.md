# Open questions

Real gaps found during live testing, deliberately not fixed yet — either because the fix is a genuine design decision, not a quick patch, or because the next step is a comparison/experiment rather than a code change. Each has a dated entry in [CLAUDE.md](../../.claude/CLAUDE.md) with the full finding; this note tracks *what to decide*, not what happened.

## HypothesisManagerAgent has no document grounding

`hypothesis_manager_agent.py`'s prompt only includes the triggering Concern's own fields (title, business_impact, what_would_change_conclusion) — never the memo, the BusinessProfile, or any raw chunk. Result on Fermento: 6 generic hypotheses ("shift in market demand", "decline in a major customer's orders") with zero connection to what the memo actually documents (supplier lead times, spoilage, cut hours).

> [!question] Decision needed
> How much context to feed in — the full BusinessProfile? Relevant chunks retrieved by some similarity/keyword match to the concern? Both risk blowing the 4096-token context further (see [[Decisions/LLM backend]]). Not a quick patch.

## BusinessUnderstandingAgent hallucinated on Fermento

Described a wine *bar* as a wine *producer* — despite the real Spanish memo being fully present in its prompt. Confirmed by reading the prompt template directly, not assumed. Looks like a local 8B model capability limit on a longer Spanish narrative, not a code defect.

> [!question] Decision needed
> Run the same Fermento scenario with `useClaude=true` and compare the business profile output directly. If Claude gets it right, this becomes a documented model-tier trade-off, not a bug to chase further in code.

## QuickAnswerService creates duplicate Findings

`answer()` calls `repo.create_finding` unconditionally for every evidence item, every call — no dedup by statement text, unlike `FinancialAnalysisService.run()` which is explicitly idempotent for this reason. Repeated questions touching the same numbers keep creating new `origin="llm"` Finding rows.

> [!question] Decision needed
> Is this actually a problem worth fixing? Each QuickAnswer's evidence arguably *should* be its own row (self-contained per answer), unlike the engine's cross-call idempotency requirement. Lean toward "leave it" unless the findings table growing unbounded becomes a real issue (e.g. for [[Decisions/LLM backend|context budget]] reasons via `_build_prior_findings_context`).

## No true background monitoring

"Continuous Monitoring" only diffs concerns/opportunities when detection is triggered while the app is open — not a real scheduled daemon. Explicitly scoped out of Phase 5, documented as a real gap, not forgotten.

> [!question] Decision needed
> Worth a launchd-based background job at all for a single-user local tool? Or is "diffed whenever you open the app" actually fine for how this gets used in practice?

See also: [[Home]]
