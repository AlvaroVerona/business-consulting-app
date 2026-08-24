# Stack: Swift + Python, not one language

> [!note] Decision
> Native SwiftUI macOS app (`App/`) for the UI, Python/FastAPI sidecar (`sidecar/`) for everything else — parsing, the deterministic financial engine, LLM orchestration, persistence. The Swift app is a thin HTTP client over `127.0.0.1:8765`.

> [!tip] Why
> Two reasons, not one.
> - Reuses working multi-agent/schema-validation patterns already proven in `~/agent-platform`, which is Python.
> - Python's document-parsing ecosystem (openpyxl, python-docx, pypdf) is meaningfully more mature than Swift's for this app's ingestion needs — a real, not theoretical, gap.

> [!warning] Trade-off accepted
> Two languages, two dependency worlds, two test suites, an IPC boundary. No Xcode project either (see [Discovery doc](../../../DISCOVERY.md)) — `App/Scripts/build-app.sh` hand-assembles the `.app` bundle instead of using Xcode's Archive flow, which is why packaging needed its own build script rather than being free.

> [!example] Where this shows up in the code
> - `App/Sources/BusinessConsultant/Services/SidecarClient.swift` — the HTTP boundary, one method per sidecar endpoint
> - `App/Scripts/build-app.sh` — the hand-rolled packaging this decision requires
> - `.github/workflows/ci.yml` — two separate jobs (`sidecar-tests`, `app-build`) because it's genuinely two projects glued together

Confirmed 2026-08-19, see [CLAUDE.md](../../.claude/CLAUDE.md)'s Phase 1 entry.

See also: [[Home]]
