#!/bin/bash

# Mac Installation Script for Screenshot Uploader
echo "🖥️  Setting up Mac Screenshot Uploader..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    echo "You can install it via Homebrew: brew install python3"
    exit 1
fi

# Install Oracle CLI if not present
if ! command -v oci &> /dev/null; then
    echo "📦 Installing Oracle CLI..."
    pip3 install oci-cli
else
    echo "✅ Oracle CLI already installed"
fi

# Install Python requirements
echo "📦 Installing Python dependencies..."
pip3 install -r requirements_mac.txt

# Create Oracle CLI config directory
mkdir -p ~/.oci

echo "✅ Mac setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Configure Oracle Cloud CLI with: oci setup config"
echo "2. Update the bucket_name in mac_screenshot_uploader.py if needed"
echo "3. Run the script with: python3 mac_screenshot_uploader.py"
echo ""
echo "🔧 To run automatically at startup, add this to your crontab:"
echo "@reboot cd $(pwd) && python3 mac_screenshot_uploader.py >> /tmp/screenshot_uploader.log 2>&1"
