#!/bin/bash
# Launch Chrome with CDP for Facebook automation
# Port 9224 (separate from TikTok 9222 and LinkedIn 9223)

set -e

PROFILE_DIR="$HOME/chrome-fb-profile"
CDP_PORT=9224

# Check if Chrome is already running with CDP
if lsof -i :$CDP_PORT >/dev/null 2>&1; then
    echo "Chrome already running on port $CDP_PORT"
    exit 0
fi

# Create profile directory if needed
mkdir -p "$PROFILE_DIR"

echo "Starting Chrome with CDP on port $CDP_PORT..."
echo "Profile: $PROFILE_DIR"

# Launch Chrome with CDP
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=$CDP_PORT \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    "https://www.facebook.com/ProCaffeGroup/videos" &

echo "Chrome launched. Log in to Facebook if needed."
echo "Then run: python3 fb-video-discovery.py"
