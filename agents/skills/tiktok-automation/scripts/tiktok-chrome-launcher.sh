#!/bin/bash
# Launch Chrome with CDP (Chrome DevTools Protocol) for TikTok automation
# Uses separate profile to isolate TikTok session from main Chrome

set -e

CDP_PORT="${TIKTOK_CDP_PORT:-9222}"
PROFILE_DIR="${TIKTOK_CHROME_PROFILE:-$HOME/chrome-tiktok-profile}"
CHROME_APP="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Check if Chrome is already running with CDP on this port
if lsof -i ":$CDP_PORT" >/dev/null 2>&1; then
    echo "Chrome already running on CDP port $CDP_PORT"
    exit 0
fi

# Create profile directory if needed
mkdir -p "$PROFILE_DIR"

echo "Launching Chrome with CDP on port $CDP_PORT..."
echo "Profile: $PROFILE_DIR"

# Launch Chrome with remote debugging enabled
# --no-first-run: Skip first run dialogs
# --disable-default-apps: Don't load default apps
# --user-data-dir: Use isolated profile
"$CHROME_APP" \
    --remote-debugging-port="$CDP_PORT" \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --disable-default-apps \
    --disable-popup-blocking \
    "https://www.tiktok.com" &

echo "Chrome launched. PID: $!"
echo ""
echo "IMPORTANT: Log in to TikTok manually on first run."
echo "After login, the session persists in: $PROFILE_DIR"
