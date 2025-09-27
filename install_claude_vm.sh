#!/bin/bash
# Installation script for Claude DSA Screenshot Watcher on Oracle VM (Linux)

echo "🚀 Installing Claude DSA Screenshot Watcher on Oracle VM..."

# Update system packages
echo "📦 Updating system packages..."
sudo yum update -y

# Install Python development tools and dependencies for Pillow
echo "🔧 Installing system dependencies..."
sudo yum groupinstall -y "Development Tools"
sudo yum install -y python3-devel libjpeg-devel zlib-devel

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements for VM (without macOS-specific packages)
echo "📋 Installing Python dependencies for VM..."
pip install -r requirements_vm.txt

echo ""
echo "✅ Installation completed successfully!"
echo ""
echo "📋 Required Environment Variables:"
echo "   export ANTHROPIC_API_KEY='your-claude-api-key'"
echo "   export TELEGRAM_BOT_TOKEN='your-telegram-bot-token'  # Optional"
echo "   export TELEGRAM_CHAT_ID='your-telegram-chat-id'      # Optional"
echo "   export NTFY_TOPIC='your-ntfy-topic'                  # Optional"
echo ""
echo "🧪 Test the installation:"
echo "   python test_claude_dsa_integration.py"
echo ""
echo "🚀 Run the Claude DSA watcher:"
echo "   python claude_dsa_screenshot_watcher.py"
echo ""
