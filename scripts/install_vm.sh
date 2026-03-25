#!/bin/bash

# Oracle VM Installation Script for Screenshot Watcher
echo "☁️  Setting up Oracle VM Screenshot Watcher..."

# Detect OS
if [ -f /etc/oracle-release ] || [ -f /etc/redhat-release ]; then
    OS="rhel"
elif [ -f /etc/debian_version ]; then
    OS="debian"
else
    echo "❌ Unsupported OS. This script supports Oracle Linux/RHEL and Debian/Ubuntu."
    exit 1
fi

# Install Python and pip
echo "📦 Installing Python and dependencies..."
if [ "$OS" = "rhel" ]; then
    sudo dnf update -y
    sudo dnf install python3 python3-pip git -y
else
    sudo apt update
    sudo apt install python3 python3-pip git -y
fi

# Install Python requirements
echo "📦 Installing Python packages..."
pip3 install --user -r requirements_vm.txt

# Add pip user bin to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create systemd service file
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/screenshot-watcher.service > /dev/null <<EOF
[Unit]
Description=Screenshot Watcher Service
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/screenshot_watcher.py
Restart=always
RestartSec=10
Environment=PATH=/usr/bin:/usr/local/bin:$HOME/.local/bin

# Environment variables (update these!)
Environment=OPENAI_API_KEY=your-openai-api-key-here
Environment=TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here
Environment=TELEGRAM_CHAT_ID=your-telegram-chat-id-here
Environment=NTFY_TOPIC=your-ntfy-topic-here

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Oracle VM setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit the environment variables in /etc/systemd/system/screenshot-watcher.service"
echo "2. Enable and start the service:"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable screenshot-watcher"
echo "   sudo systemctl start screenshot-watcher"
echo ""
echo "📊 To check service status:"
echo "   sudo systemctl status screenshot-watcher"
echo "   sudo journalctl -u screenshot-watcher -f"
