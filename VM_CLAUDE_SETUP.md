# Claude DSA Screenshot Watcher - VM Setup Guide

## 🚀 Quick Setup for Oracle VM (Linux)

### 1. Install Dependencies

Run the automated installation script:

```bash
chmod +x install_claude_vm.sh
./install_claude_vm.sh
```

Or install manually:

```bash
# Install system dependencies
sudo yum groupinstall -y "Development Tools"
sudo yum install -y python3-devel libjpeg-devel zlib-devel

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages (VM-specific, no macOS dependencies)
pip install -r requirements_vm.txt
```

### 2. Set Environment Variables

```bash
# Required: Claude API Key
export ANTHROPIC_API_KEY="your-claude-api-key-here"

# Optional: Notification services
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export TELEGRAM_CHAT_ID="your-telegram-chat-id"
export NTFY_TOPIC="your-ntfy-topic"
```

### 3. Test the Setup

```bash
# Test Claude API integration
python test_claude_dsa_integration.py
```

### 4. Run the Claude DSA Watcher

```bash
# Start the main watcher (processes 3 screenshots at a time)
python claude_dsa_screenshot_watcher.py
```

## 🔧 What's Different from Mac Version

- **No macOS dependencies**: Removed `pyobjc-framework-Cocoa` and `pyobjc-framework-Quartz`
- **VM-optimized**: Uses `requirements_vm.txt` instead of `requirements_mac.txt`
- **Same functionality**: All DSA processing features work identically

## 📋 Dependencies Installed

- `oci==2.112.1` - Oracle Cloud SDK
- `anthropic==0.66.0` - Claude API client
- `requests==2.31.0` - HTTP requests
- `Pillow>=10.4.0` - Image processing (for compression)
- `python-telegram-bot==20.7` - Telegram notifications
- `openai==1.3.8` - (Legacy, for compatibility)

## 🎯 Key Features

- **Batch Processing**: Processes 3 screenshots together
- **Image Compression**: Automatically compresses large images under 5MB limit
- **Claude 4 Sonnet**: Uses `claude-3-5-sonnet-20250514` model
- **Smart Prompting**: Asks Claude to read problems and provide Python solutions
- **Failed Test Fix**: Handles failed test cases from screenshots
- **Multi-approach**: Provides multiple solution approaches with complexity analysis

## 🔍 Troubleshooting

### Common Issues:

1. **Missing system dependencies**:
   ```bash
   sudo yum install python3-devel libjpeg-devel zlib-devel
   ```

2. **Pillow installation fails**:
   ```bash
   sudo yum groupinstall "Development Tools"
   pip install --upgrade pip setuptools wheel
   ```

3. **Claude API errors**:
   - Verify `ANTHROPIC_API_KEY` is set correctly
   - Check API key has sufficient credits

### Log Files:

- Main log: `/tmp/claude_dsa_screenshot_watcher.log`
- Solutions saved to: `/tmp/claude_dsa_solutions/`

## 🚀 Usage

Once running, the watcher will:

1. Monitor Oracle Cloud Object Storage for new screenshots
2. Download screenshots in batches of 3
3. Compress images if they exceed 4.5MB
4. Send to Claude 4 Sonnet for DSA problem solving
5. Generate comprehensive Python solutions
6. Save solutions to files and send notifications

Upload screenshots to your Oracle Cloud bucket and watch the magic happen! 🎉
