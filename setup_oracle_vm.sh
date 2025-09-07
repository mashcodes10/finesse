#!/bin/bash

# Oracle VM Setup Script for Screenshot Processing
echo "🔧 Setting up Oracle VM for screenshot processing..."

# Check if running on Oracle Linux or Ubuntu
if [ -f /etc/oracle-release ] || [ -f /etc/redhat-release ]; then
    DISTRO="oracle"
    PKG_MANAGER="dnf"
elif [ -f /etc/debian_version ]; then
    DISTRO="ubuntu"
    PKG_MANAGER="apt"
else
    echo "❌ Unsupported OS"
    exit 1
fi

echo "📋 Detected OS: $DISTRO"

# Update system
echo "📦 Updating system packages..."
if [ "$DISTRO" = "oracle" ]; then
    sudo dnf update -y
    sudo dnf install python3 python3-pip git wget curl -y
else
    sudo apt update
    sudo apt install python3 python3-pip git wget curl -y
fi

# Install Python packages
echo "🐍 Installing Python packages..."
pip3 install --user oci openai==1.3.8 requests pillow python-telegram-bot

# Add pip user bin to PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create project directory
mkdir -p ~/finesse
cd ~/finesse

echo "✅ Basic setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Set your OpenAI API key:"
echo "   export OPENAI_API_KEY=sk-your-api-key-here"
echo ""
echo "2. Upload the screenshot_watcher.py script to this directory"
echo ""
echo "3. Test the setup:"
echo "   python3 -c \"import oci, openai; print('✅ Packages installed')\""
