# LLM backend: hybrid, local by default

**Decision:** local Ollama (`llama3.1`) is the default for every LLM call. Claude API is available only as an explicit per-call opt-in (`use_claude` / `useClaude`) — never a silent default. Lives in `sidecar/src/llm/router.py`.

**Why:** consistent with the standing rule from Ballesta4 (see `project_ballesta4_free_llms` in memory) — no paid API by default. Deep Analysis is where paying for Claude's stronger reasoning would matter most, so it's opt-in there specifically, not app-wide.

**What this costs in practice:** local `llama3.1` (8B, quantized) has real, repeatedly-observed limitations — not hypothetical ones:
- Arithmetic errors on multi-step calculations (the reason the deterministic financial engine exists at all — [CLAUDE.md](../../.claude/CLAUDE.md)'s original Phase 2 entry)
- JSON that isn't quite JSON: Python `None`/`True`/`False` instead of `null`/`true`/`false`, single-quoted dict literals — `llm/json_utils.py`'s `_normalize_python_literals` exists only because of this
- Near-total hallucination on a longer Spanish-language business profile (described Fermento, a wine *bar*, as a wine *producer* — "vineyard maintenance", "wine clubs") despite the real memo being fully in its prompt context. Not yet compared against `useClaude=true` on the same input — that comparison is still open, see [[Backlog/Open questions]].
- A small (4096-token) context window on the actual running model (`ps aux | grep llama-server` shows `-c 4096 --context-shift`), which silently discards early context under pressure rather than erroring

None of these are edge cases anymore — they're the normal operating conditions of this backend. Every deterministic-engine addition in this project (financial calculations, cross-period totals) exists specifically to keep arithmetic and lookups out of the LLM's hands, not because it was a nice-to-have.

See also: [[Home]]
