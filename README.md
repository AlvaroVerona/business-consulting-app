# Business Consulting App

[![CI](https://github.com/AlvaroVerona/business-consulting-app/actions/workflows/ci.yml/badge.svg)](https://github.com/AlvaroVerona/business-consulting-app/actions/workflows/ci.yml)

AI-powered business consulting / strategy-analysis macOS app. Spec: `../CLAUDE_CODE_BUSINESS_CONSULTING_SPEC.md`. Discovery notes and architecture decisions: `../DISCOVERY.md`. MVP (spec section 18's Definition of Done, 13/13) complete as of 2026-08-19 — see `.claude/CLAUDE.md` for the full build history.

## Stack

- **`App/`** — native SwiftUI macOS app (Swift Package Manager executable target).
- **`sidecar/`** — local Python backend (FastAPI + SQLAlchemy). Owns document parsing, deterministic calculations, LLM orchestration, and persistence. The Swift app talks to it over `http://127.0.0.1:8765`.

## Why two languages

Documented in `../DISCOVERY.md` under "Proposed Technical Architecture". Short version: reuses working multi-agent/schema-validation patterns from `~/agent-platform`, and Python's document-parsing ecosystem (openpyxl, python-docx, pypdf) is more mature than Swift's for this product's ingestion requirements.

## LLM backend

Hybrid (decided 2026-08-19): local Ollama (`llama3.1`) is the default for every call. The Claude API is available as an opt-in backend per request — never a silent default — for calls where reasoning quality matters more than cost. See `sidecar/src/llm/router.py`.

## Running the sidecar

The packaged `.app` (see below) starts this automatically — you only need to run it by hand for sidecar development (`--reload`) or when using `swift run` directly:

```bash
cd sidecar
uv sync
uv run uvicorn src.main:app --reload --port 8765
```

## Running the tests

```bash
cd sidecar
uv run pytest
```

All 131 sidecar tests are hermetic — LLM calls go through `FakeLLM` stand-ins, never real Ollama/Claude requests, so they run the same in CI as locally. There's no equivalent automated test suite for the Swift app yet; CI's `app-build` job only verifies it still compiles and packages (`.github/workflows/ci.yml`), not that it behaves correctly.

## Running the macOS app

For development (rebuilds on every change, runs from Terminal — you need the sidecar running separately, see above):

```bash
cd App
swift run
```

As a real, double-clickable app: this project is a Swift Package, not an Xcode project (see `../DISCOVERY.md` for why), so there's no Xcode-managed `.app` bundle — `App/Scripts/build-app.sh` assembles one by hand from the SwiftPM release build, with a generated icon (`App/Resources/AppIcon.icns`, source: `App/Scripts/generate_icon.swift`) and `Info.plist`, ad-hoc code-signed for local use:

```bash
cd App
./Scripts/build-app.sh
open .build/app/BusinessConsultant.app          # launch it
cp -R .build/app/BusinessConsultant.app /Applications/   # or install it
```

**The packaged app auto-starts the sidecar** (`SidecarLauncher.swift`): on launch it checks `http://127.0.0.1:8765/health`, and if nothing answers, spawns `uv run uvicorn` itself, pointed at the sidecar's source directory (fixed to `~/Documents/ai_for_business/business-consulting-app/sidecar` by default — override with the `BUSINESS_CONSULTANT_SIDECAR_PATH` env var if the repo lives somewhere else; this is a personal, single-machine tool, not built to auto-locate itself on other systems). It only stops the sidecar it actually spawned when the app quits — one it finds already running (started manually, or by another launch of the app) is left alone. Needs `uv` installed at one of `~/.local/bin/uv`, `/opt/homebrew/bin/uv`, or `/usr/local/bin/uv` — a GUI-launched app doesn't inherit your shell's `PATH`, so it won't find `uv` there even if `which uv` works fine in Terminal.

Ad-hoc signed only (not notarized — that needs an Apple Developer account this project doesn't use), so it's for running on this machine, not for distributing to others.
