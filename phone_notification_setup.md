# Phone Notification Setup Guide

This guide covers setting up both **ntfy.sh** and **Telegram bot** notifications for receiving Python code extractions on your phone.

## Option 1: ntfy.sh (Recommended for simplicity)

ntfy.sh is a simple, open-source notification service that works without registration.

### 1. Install ntfy App on Your Phone

- **Android**: Download from [Google Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
- **iOS**: Download from [App Store](https://apps.apple.com/us/app/ntfy/id1625396347)

### 2. Choose a Unique Topic

Pick a unique topic name (like `yourname-screenshot-code-123456`). This will be your notification channel.

### 3. Subscribe to Topic on Phone

1. Open the ntfy app
2. Tap the "+" button
3. Enter your topic name (e.g., `yourname-screenshot-code-123456`)
4. Tap "Subscribe"

### 4. Configure Environment Variable on Oracle VM

```bash
export NTFY_TOPIC=yourname-screenshot-code-123456
```

### 5. Test the Setup

```bash
# Test from your Oracle VM
curl -d "Test message from Oracle VM" ntfy.sh/yourname-screenshot-code-123456
```

You should receive a notification on your phone immediately.

## Option 2: Telegram Bot

Telegram provides richer formatting and file sharing capabilities.

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Start a chat with BotFather
3. Send `/newbot`
4. Follow the prompts to create your bot
5. Save the **Bot Token** (format: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2. Get Your Chat ID

1. Start a chat with your newly created bot
2. Send any message to the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Look for `"chat":{"id":XXXXXXX` - this number is your Chat ID

### 3. Configure Environment Variables on Oracle VM

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
export TELEGRAM_CHAT_ID=your-chat-id-number
```

### 4. Test the Setup

```bash
# Test from your Oracle VM
curl -X POST \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\": \"${TELEGRAM_CHAT_ID}\", \"text\": \"Test message from Oracle VM\"}"
```

## Option 3: Both (Recommended)

You can configure both notification methods for redundancy:

```bash
# Set both environment variables
export NTFY_TOPIC=yourname-screenshot-code-123456
export TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
export TELEGRAM_CHAT_ID=your-chat-id-number
```

The screenshot watcher will automatically use both methods when available.

## Setting Environment Variables Permanently

Add these to your shell profile on the Oracle VM:

```bash
# Edit your shell profile
vim ~/.bashrc  # or ~/.zshrc

# Add these lines at the end:
export OPENAI_API_KEY=your-openai-api-key
export NTFY_TOPIC=yourname-screenshot-code-123456
export TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
export TELEGRAM_CHAT_ID=your-chat-id-number

# Reload the profile
source ~/.bashrc
```

## Notification Features

### ntfy.sh Features:
- ✅ Instant notifications
- ✅ No registration required
- ✅ Works on Android and iOS
- ✅ Code preview (truncated for long files)
- ✅ Custom icons and priorities
- ❌ Limited file sharing

### Telegram Features:
- ✅ Instant notifications
- ✅ Rich markdown formatting
- ✅ Full file sharing (.py files)
- ✅ Message history
- ✅ Works on all platforms
- ✅ Bot can be added to groups
- ❌ Requires bot setup

## Notification Format

### ntfy.sh Notification:
```
🖥️ Screenshot Code Extracted

🐍 Python Code Extracted!

📸 From: screenshot_20240101_143022.png
📝 Saved as: screenshot_20240101_143022_20240101_143025.py
⏰ Time: 2024-01-01 14:30:25
```

### Telegram Notification:
```
🐍 **Python Code Extracted!**

📸 From: `screenshot_20240101_143022.png`
📝 Saved as: `screenshot_20240101_143022_20240101_143025.py`
⏰ Time: 2024-01-01 14:30:25

[📄 screenshot_20240101_143022_20240101_143025.py] (file attachment)
```

## Troubleshooting

### ntfy.sh Issues:
1. **Not receiving notifications**: Check if you subscribed to the correct topic
2. **Topic not working**: Try a different, more unique topic name
3. **App not installed**: Make sure you have the official ntfy app

### Telegram Issues:
1. **Bot not responding**: Verify the bot token is correct
2. **Wrong chat ID**: Get chat ID again from `/getUpdates`
3. **API errors**: Check bot permissions and token validity

### General Issues:
1. **Environment variables not set**: Check with `echo $NTFY_TOPIC`
2. **Network issues**: Test with curl commands
3. **Oracle VM firewall**: Ensure outbound HTTPS is allowed
