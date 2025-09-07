# 🖥️ Mac Screenshot Code Analyzer

An automated pipeline that captures your Mac screenshots, uploads them to Oracle Cloud, extracts Python code using OpenAI Vision API, and delivers the results to your phone in real-time.

## 🌟 Features

- **🤫 Silent Screenshots**: Captures your Mac screen every 5 minutes without sound
- **☁️ Cloud Storage**: Automatic upload to Oracle Cloud Object Storage
- **🤖 AI Code Extraction**: Uses OpenAI's Vision API to extract only Python code
- **📱 Real-time Notifications**: Delivers extracted code to your phone via ntfy.sh or Telegram
- **🆓 Cost-Effective**: Runs entirely on Oracle Cloud Free Tier

## 🏗️ Architecture

```
[Mac] → [Screenshot] → [Oracle Cloud Storage] → [Oracle VM] → [OpenAI Vision] → [Phone]
   ↓        Every 5min         ↓                    Polls         ↓              ↓
Screenshots  Silent capture     Bucket            Watcher      Code Extract   Notifications
```

## 📁 Project Structure

```
finesse/
├── mac_screenshot_uploader.py    # Mac screenshot automation
├── screenshot_watcher.py          # Oracle VM watcher script
├── requirements_mac.txt           # Mac dependencies
├── requirements_vm.txt            # VM dependencies
├── install_mac.sh                 # Mac installation script
├── install_vm.sh                  # VM installation script
├── oracle_cloud_setup.md          # Oracle Cloud configuration guide
├── phone_notification_setup.md    # Phone notification setup
├── DEPLOYMENT_GUIDE.md            # Complete deployment instructions
└── README.md                      # This file
```

## 🚀 Quick Start

### 1. Mac Setup
```bash
cd finesse
chmod +x install_mac.sh
./install_mac.sh
```

### 2. Oracle Cloud Setup
Follow the detailed instructions in `oracle_cloud_setup.md`

### 3. Oracle VM Setup
```bash
# On your Oracle VM
git clone <repo-url> finesse
cd finesse
chmod +x install_vm.sh
./install_vm.sh
```

### 4. Phone Notifications
Follow the setup guide in `phone_notification_setup.md`

### 5. Start the Pipeline
```bash
# On Mac
python3 mac_screenshot_uploader.py

# On Oracle VM (automatic via systemd)
sudo systemctl start screenshot-watcher
```

## 📋 Prerequisites

- **Mac**: macOS 10.14+ with Python 3.7+
- **Oracle Cloud**: Free tier account
- **OpenAI**: API key with GPT-4 Vision access
- **Phone**: ntfy app or Telegram

## 🔧 Configuration

### Environment Variables (Oracle VM)
```bash
export OPENAI_API_KEY=sk-your-openai-api-key
export TELEGRAM_BOT_TOKEN=your-telegram-bot-token  # Optional
export TELEGRAM_CHAT_ID=your-telegram-chat-id      # Optional
export NTFY_TOPIC=your-unique-ntfy-topic          # Optional
```

### Oracle CLI Configuration (Mac)
```bash
oci setup config
# Follow prompts to configure API access
```

## 📊 Monitoring

### Check Mac Screenshot Status
```bash
tail -f /tmp/screenshot_uploader.log
```

### Check Oracle VM Watcher Status
```bash
sudo systemctl status screenshot-watcher
sudo journalctl -u screenshot-watcher -f
```

## 🛠️ Troubleshooting

### Common Issues

1. **Permission Denied (Mac)**
   - Grant screen recording permission: System Preferences → Security & Privacy → Privacy → Screen Recording

2. **Oracle Upload Fails**
   - Check API key configuration
   - Verify internet connection
   - Confirm bucket exists

3. **No Notifications**
   - Verify phone notification setup
   - Check Oracle VM internet access
   - Confirm OpenAI API key is valid

4. **Service Won't Start (VM)**
   - Check environment variables in systemd service
   - Verify Python dependencies are installed
   - Check logs for specific error messages

### Log Locations
- **Mac**: `/tmp/screenshot_uploader.log`
- **Oracle VM**: `sudo journalctl -u screenshot-watcher`

## 💰 Cost Considerations

### Oracle Cloud Free Tier
- ✅ 20GB Object Storage
- ✅ VM.Standard.E2.1.Micro compute
- ✅ 10TB outbound data transfer/month

### OpenAI API Costs
- GPT-4 Vision: ~$0.01-0.03 per image
- Monitor usage in OpenAI dashboard

## 🔒 Security Notes

- **API Keys**: Store securely, never commit to version control
- **Screenshots**: May contain sensitive information
- **ntfy Topics**: Use unique, hard-to-guess names (topics are public)
- **SSH Access**: Use key-based authentication only

## 🎯 Use Cases

- **Code Review**: Automatically capture and analyze code snippets
- **Learning**: Track coding progress and patterns
- **Documentation**: Extract code examples for tutorials
- **Debugging**: Capture error states and problematic code
- **Sharing**: Quickly send formatted code to mobile devices

## 🔄 Workflow Example

1. **14:00** - Write Python function in VS Code
2. **14:05** - Mac takes silent screenshot
3. **14:05** - Screenshot uploaded to Oracle Cloud
4. **14:05** - Oracle VM detects new screenshot
5. **14:06** - OpenAI extracts Python code
6. **14:06** - Code saved as `.py` file on VM
7. **14:06** - Phone receives notification with formatted code

## 🤝 Contributing

Feel free to submit issues, feature requests, or pull requests to improve the system.

## 📜 License

This project is open source and available under the MIT License.

---

**Happy Coding!** 🐍✨
