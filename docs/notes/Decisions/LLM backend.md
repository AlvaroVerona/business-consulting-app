# LLM backend: hybrid, local by default

> [!note] Decision
> Local Ollama (`llama3.1`) is the default for every LLM call. Claude API is available only as an explicit per-call opt-in (`use_claude` / `useClaude`) — never a silent default. Lives in `sidecar/src/llm/router.py`.

> [!tip] Why
> Consistent with a standing rule across my projects — no paid API by default. Deep Analysis is where paying for Claude's stronger reasoning would matter most, so it's opt-in there specifically, not app-wide.

> [!bug] What this costs in practice
> Local `llama3.1` (8B, quantized) has real, repeatedly-observed limitations — not hypothetical ones:
> - Arithmetic errors on multi-step calculations (the reason the deterministic financial engine exists at all — [CLAUDE.md](../ENGINEERING_LOG.md)'s original Phase 2 entry)
> - JSON that isn't quite JSON: Python `None`/`True`/`False` instead of `null`/`true`/`false`, single-quoted dict literals — `llm/json_utils.py`'s `_normalize_python_literals` exists only because of this
None of these are edge cases anymore — they're the normal operating conditions of this backend. Every deterministic-engine addition in this project (financial calculations, cross-period totals) exists specifically to keep arithmetic and lookups out of the LLM's hands, not because it was a nice-to-have.

> [!success] Resolved 2026-08-28: the "hallucination" was a context-window bug, not a model limit
> The near-total hallucination on Fermento's business profile (described a wine *bar* as a wine *producer*) turned out to be caused by `ollama_client.py` never setting `num_ctx` — Ollama's real default (4096, confirmed live via `ollama ps`) silently truncated the prompt rather than erroring, and the real Fermento chunk dump alone measured ~4171 tokens, already over that budget. Bumped the client's default to 8192 (`OLLAMA_NUM_CTX` env override). Re-ran the same Fermento profile live afterward: correctly identifies it as a wine bar in Malasaña. No `useClaude=true` comparison was needed — see [CLAUDE.md](../ENGINEERING_LOG.md)'s "Root cause found for two open items" entry.

See also: [[Home]]
