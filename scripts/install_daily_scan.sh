#!/bin/bash
# Installs a macOS launchd job that runs the podcast signal scanner every day
# at 7:30 AM — no Electron app open, no terminal session needed. If the Mac is
# asleep at 7:30, launchd runs the job on next wake. The agent's own run-lock
# prevents double-runs if the app's scheduler also fires.
#
# Usage:   bash scripts/install_daily_scan.sh
# Remove:  launchctl unload ~/Library/LaunchAgents/com.atlas.podcast-scan.plist \
#          && rm ~/Library/LaunchAgents/com.atlas.podcast-scan.plist
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$REPO/agents/podcast"
PYTHON="$AGENT_DIR/.venv/bin/python3"
PLIST="$HOME/Library/LaunchAgents/com.atlas.podcast-scan.plist"
LOG="$HOME/Library/Logs/atlas-podcast-scan.log"

if [ ! -x "$PYTHON" ]; then
  echo "ERROR: venv python not found at $PYTHON — run the setup in agents/README.md first."
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.atlas.podcast-scan</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$AGENT_DIR/podcast_intel_agent.py</string>
  </array>
  <key>WorkingDirectory</key><string>$AGENT_DIR</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>EnvironmentVariables</key>
  <dict><key>PYTHONUNBUFFERED</key><string>1</string></dict>
</dict>
</plist>
PLIST

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed. Daily scan at 7:30 AM (runs on wake if the Mac was asleep)."
echo "Log: $LOG"
echo "Run immediately to test:  launchctl start com.atlas.podcast-scan"
