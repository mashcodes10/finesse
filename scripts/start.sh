#!/bin/bash
# Run both Finesse services silently in the background

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

pkill -f mac_screenshot_daemon.py 2>/dev/null
pkill -f overlay_display.py 2>/dev/null

nohup python3 "$SCRIPT_DIR/mac_screenshot_daemon.py" start > /tmp/finesse_daemon.log 2>&1 &
nohup python3 "$SCRIPT_DIR/overlay_display.py" > /tmp/finesse_overlay.log 2>&1 &

echo "Finesse is running silently."
