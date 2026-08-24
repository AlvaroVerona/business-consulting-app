# Fermento — the live test scenario

Fictional business built specifically to exercise the app against something non-trivial: a natural-wine bar in Malasaña, Madrid, run by two technically-trained founders, hit by a real compounding-cause slump (supplier delays, opened-bottle spoilage, seasonal Madrid-in-August effect, reduced hours). Full fixture — memo, financials, wine list, OPEX breakdown, and exact replication steps — lives at [manual-tests/fermento-winebar/](../../manual-tests/fermento-winebar/README.md), committed so this is re-runnable, not a one-off.

> [!tip] Why fictional-but-non-trivial, not a toy dataset
> The app's hermetic pytest suite already covers correctness against `FakeLLM` stand-ins. This scenario exists to answer a different question — is the output actually *useful*, run against the real local model — and a toy dataset with obvious answers wouldn't stress that.

> [!bug] What it's found so far
> Every one of these was found by actually asking the app real questions against this data and checking the answer against a hand-computed ground truth, not by reading code. See [CLAUDE.md](../../.claude/CLAUDE.md) for the full dated write-up of each.
> - `coste_ventas` (Peninsular Spanish) not recognized as COGS — only `costo_de_ventas` (Latin American Spanish) was
> - Concern/opportunity detection blind to a rise-then-fall ("mixed") trend — a 13pt margin drop produced zero alerts
> - Citation validation accepted a chunk_id from one document paired with a different document's document_id
> - `extract_json` choked on Python `None`/`True`/`False` and single-quoted dict literals
> - 60s client-side timeout too short for a local model with a retry loop + possible cold start
> - No preview of uploaded documents at all (fixed via Quick Look)
> - Asking for a total (OPEX, COGS) got a wildly wrong number — the LLM had to sum periods itself with no deterministic total to reuse
> - `recommended_next_question` silently empty most of the time — no prompt instruction ever told the model what it was for

> [!question] Still open
> See [[Backlog/Open questions]] — the two Deep Analysis findings (hallucinated business profile, ungrounded hypotheses) haven't been fixed yet, just documented.

See also: [[Home]]
