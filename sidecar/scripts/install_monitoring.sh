#!/bin/bash
# Installs a per-user launchd LaunchAgent that runs run_monitoring.py on a
# schedule (spec section 15 Phase 5, "Continuous Monitoring" — see
# ../../notes/Backlog/Open questions.md for why this didn't exist before).
# LaunchAgent, not LaunchDaemon: this only needs to run while Álvaro is
# logged in, and a LaunchDaemon would need root/sudo for a personal,
# single-machine tool that doesn't warrant it.
set -euo pipefail

SIDECAR_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.alvaroverona.businessconsultant.monitoring"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_PATH="/tmp/business-consultant-monitoring.log"
INTERVAL_SECONDS=21600  # 6 hours — frequent enough to catch same-day changes, not excessive for a personal tool with no real-time requirement

# A launchd agent's environment doesn't include the interactive shell's
# PATH any more than a GUI-launched app's does (see the App-side
# SidecarLauncher.swift's resolveUvExecutable(), same reasoning) — `uv`
# has to be resolved to an absolute path here, not just called by name.
UV_PATH=""
for candidate in "$HOME/.local/bin/uv" "/opt/homebrew/bin/uv" "/usr/local/bin/uv"; do
    if [ -x "$candidate" ]; then
        UV_PATH="$candidate"
        break
    fi
done

if [ -z "$UV_PATH" ]; then
    echo "error: uv not found at any known location (~/.local/bin, /opt/homebrew/bin, /usr/local/bin)" >&2
    exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_DEST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>WorkingDirectory</key>
    <string>${SIDECAR_DIR}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${UV_PATH}</string>
        <string>run</string>
        <string>python</string>
        <string>-m</string>
        <string>scripts.run_monitoring</string>
    </array>
    <key>StartInterval</key>
    <integer>${INTERVAL_SECONDS}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_PATH}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_PATH}</string>
</dict>
</plist>
PLIST

# bootout before bootstrap so re-running this script (e.g. after editing
# the interval) updates a job that's already loaded, instead of erroring
# on a duplicate Label. bootout on a job that isn't loaded yet just fails
# harmlessly -- that's expected on first install, not a real error.
launchctl bootout "gui/$(id -u)" "$PLIST_DEST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"

echo "Installed: ${LABEL}"
echo "Runs every $((INTERVAL_SECONDS / 3600))h, plus once immediately now (RunAtLoad)."
echo "Log: ${LOG_PATH}"
echo "Force a run right now: launchctl kickstart -k gui/$(id -u)/${LABEL}"
echo "Uninstall: scripts/uninstall_monitoring.sh"
