# Business Consulting App — Vault

Notes vault for this repo, kept inside it so it's versioned with git instead of living somewhere disconnected. It doesn't duplicate the build history — `.claude/CLAUDE.md` stays the single source of truth for that. This vault is for the things a dated changelog isn't good at: decisions with their *why* pulled out on their own page, open questions that don't belong to any one commit, and testing notes.

## Map

- [[Decisions/Stack]] — why Swift + Python, not one language
- [[Decisions/LLM backend]] — hybrid local/Claude decision
- [[Testing/Fermento scenario]] — the wine-bar test scenario and what it's for
- [[Backlog/Open questions]] — real gaps found live, flagged but not fixed yet

> [!info] Source of truth (outside this vault)
> These links point outside the `notes/` folder — Obsidian will open them, but won't track backlinks to them the way it does for notes inside the vault.
> - [Build history / changelog](../.claude/CLAUDE.md) — every phase, every bug found and fixed, dated
> - [Discovery doc](../../DISCOVERY.md) — the Phase 1 recommendation matrix and architecture rationale
> - [Full spec](../../CLAUDE_CODE_BUSINESS_CONSULTING_SPEC.md)
> - [Fermento fixture README](../manual-tests/fermento-winebar/README.md) — the live-test scenario, replication steps
> - [README](../README.md)
