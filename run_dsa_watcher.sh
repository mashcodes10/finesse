#!/bin/bash

# DSA Screenshot Watcher Startup Script
# This script activates the virtual environment and runs the DSA screenshot watcher

echo "🔥 Starting DSA Coding Problem Screenshot Watcher..."
echo "📸 Will process screenshots in batches of 4 for comprehensive solutions"
echo "🚀 Enhanced for DSA problems, failed test case fixes, and optimized solutions"
echo ""

# Navigate to the project directory
cd "$(dirname "$0")"

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if required environment variables are set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY environment variable is not set"
    echo "   Please set it with: export OPENAI_API_KEY='your-api-key'"
    exit 1
fi

# Optional notification variables (will warn if not set but won't exit)
if [ -z "$TELEGRAM_BOT_TOKEN" ] && [ -z "$NTFY_TOPIC" ]; then
    echo "⚠️  Warning: No notification methods configured"
    echo "   Set TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID for Telegram notifications"
    echo "   Or set NTFY_TOPIC for ntfy.sh notifications"
    echo ""
fi

# Run the DSA screenshot watcher
echo "🚀 Starting DSA Screenshot Watcher..."
echo "📂 Solutions will be saved to: /tmp/dsa_solutions/"
echo "📝 Logs will be saved to: /tmp/dsa_screenshot_watcher.log"
echo ""
echo "🔥 Ready to solve DSA problems! Upload 4 screenshots to trigger batch processing."
echo "   Press Ctrl+C to stop"
echo ""

python3 dsa_screenshot_watcher.py
