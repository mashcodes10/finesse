#!/bin/bash
# Finesse Service Manager
# Usage: ./finesse_service.sh [install|uninstall|start|stop|status]

PLIST_DIR="$HOME/Library/LaunchAgents"
DAEMON_PLIST="com.finesse.daemon.plist"
OVERLAY_PLIST="com.finesse.overlay.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="$SCRIPT_DIR/config"

install() {
    echo "Installing Finesse services..."
    cp "$CONFIG_DIR/$DAEMON_PLIST" "$PLIST_DIR/"
    cp "$CONFIG_DIR/$OVERLAY_PLIST" "$PLIST_DIR/"
    launchctl load "$PLIST_DIR/$DAEMON_PLIST"
    launchctl load "$PLIST_DIR/$OVERLAY_PLIST"
    echo "Done. Finesse daemon and overlay are now running silently."
    echo "They will auto-start on every login."
}

uninstall() {
    echo "Removing Finesse services..."
    launchctl unload "$PLIST_DIR/$DAEMON_PLIST" 2>/dev/null
    launchctl unload "$PLIST_DIR/$OVERLAY_PLIST" 2>/dev/null
    rm -f "$PLIST_DIR/$DAEMON_PLIST"
    rm -f "$PLIST_DIR/$OVERLAY_PLIST"
    echo "Done. Finesse services removed."
}

start() {
    launchctl load "$PLIST_DIR/$DAEMON_PLIST" 2>/dev/null
    launchctl load "$PLIST_DIR/$OVERLAY_PLIST" 2>/dev/null
    echo "Finesse services started."
}

stop() {
    launchctl unload "$PLIST_DIR/$DAEMON_PLIST" 2>/dev/null
    launchctl unload "$PLIST_DIR/$OVERLAY_PLIST" 2>/dev/null
    echo "Finesse services stopped."
}

status() {
    echo "=== Finesse Service Status ==="
    if launchctl list | grep -q "com.finesse.daemon"; then
        echo "Daemon:  RUNNING"
    else
        echo "Daemon:  STOPPED"
    fi
    if launchctl list | grep -q "com.finesse.overlay"; then
        echo "Overlay: RUNNING"
    else
        echo "Overlay: STOPPED"
    fi
    echo ""
    echo "Logs:"
    echo "  Daemon:  /tmp/finesse_daemon_stderr.log"
    echo "  Overlay: /tmp/finesse_overlay_stderr.log"
}

case "$1" in
    install)   install ;;
    uninstall) uninstall ;;
    start)     start ;;
    stop)      stop ;;
    status)    status ;;
    *)
        echo "Usage: $0 [install|uninstall|start|stop|status]"
        echo ""
        echo "  install   — copy plists to LaunchAgents and start (runs on every login)"
        echo "  uninstall — remove from LaunchAgents and stop"
        echo "  start     — start services"
        echo "  stop      — stop services"
        echo "  status    — check if running"
        ;;
esac
