#!/bin/bash
# Removes the launchd LaunchAgent installed by install_monitoring.sh.
# Doesn't touch any data it created (Findings, Concerns, Opportunities,
# MonitoringEvents stay in the database) -- only stops future scheduled runs.
set -euo pipefail

LABEL="com.alvaroverona.businessconsultant.monitoring"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"

launchctl bootout "gui/$(id -u)" "$PLIST_DEST" 2>/dev/null || true
rm -f "$PLIST_DEST"

echo "Uninstalled: ${LABEL}"
