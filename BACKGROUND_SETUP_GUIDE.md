# 🔄 Background Services Setup Guide

## Overview

For the screenshot analysis system to work continuously, you need:

1. **Mac Screenshot Daemon**: Captures screenshots when triggered → uploads to Oracle Cloud
2. **Oracle VM Watcher**: Monitors bucket → processes with OpenAI → extracts code

Both need to run continuously in the background.

## 🖥️ Mac Side Setup

### Option 1: Terminal Session (Simple)
```bash
# Start in background with nohup
cd /Users/md.mashiurrahmankhan/Downloads/projects/finesse
source venv/bin/activate
nohup python3 mac_screenshot_daemon.py start > /tmp/mac_daemon.log 2>&1 &

# Check if it's running
python3 mac_screenshot_daemon.py status
```

### Option 2: LaunchAgent (Auto-start on boot)
```bash
# Create LaunchAgent plist
cat > ~/Library/LaunchAgents/com.finesse.screenshot.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.finesse.screenshot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/python3</string>
        <string>/Users/md.mashiurrahmankhan/Downloads/projects/finesse/mac_screenshot_daemon.py</string>
        <string>start</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/md.mashiurrahmankhan/Downloads/projects/finesse</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/screenshot_daemon.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/screenshot_daemon_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

# Load the service
launchctl load ~/Library/LaunchAgents/com.finesse.screenshot.plist

# Start the service
launchctl start com.finesse.screenshot
```

### Mac Management Commands
```bash
# Check status
python3 mac_screenshot_daemon.py status

# Stop daemon
python3 mac_screenshot_daemon.py stop

# Restart daemon
python3 mac_screenshot_daemon.py restart

# View logs
tail -f /tmp/screenshot_daemon.log
```

## ☁️ Oracle VM Side Setup

### Option 1: Screen/Tmux Session (Persistent SSH)
```bash
# SSH to VM
ssh -i ~/.ssh/your-key opc@your-vm-ip

# Install screen or tmux
sudo dnf install screen -y  # Oracle Linux
# sudo apt install screen -y  # Ubuntu

# Start a persistent session
screen -S screenshot-watcher

# In the screen session:
cd finesse
export ANTHROPIC_API_KEY=your-anthropic-api-key-here
python3 screenshot_watcher.py

# Detach from screen: Ctrl+A, then D
# Reattach later: screen -r screenshot-watcher
```

### Option 2: Systemd Service (Auto-start, most robust)
```bash
# Create systemd service file
sudo tee /etc/systemd/system/screenshot-watcher.service > /dev/null << 'EOF'
[Unit]
Description=Screenshot Watcher Service
After=network.target

[Service]
Type=simple
User=opc
WorkingDirectory=/home/opc/finesse
ExecStart=/usr/bin/python3 /home/opc/finesse/screenshot_watcher.py
Restart=always
RestartSec=10
Environment=PATH=/usr/bin:/usr/local/bin:/home/opc/.local/bin
Environment=ANTHROPIC_API_KEY=your-anthropic-api-key-here

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable screenshot-watcher
sudo systemctl start screenshot-watcher

# Check status
sudo systemctl status screenshot-watcher
```

### Oracle VM Management Commands
```bash
# Check systemd service
sudo systemctl status screenshot-watcher
sudo systemctl restart screenshot-watcher
sudo systemctl stop screenshot-watcher

# View logs
sudo journalctl -u screenshot-watcher -f

# Or if using screen/tmux
screen -list
screen -r screenshot-watcher
```

## ⚠️ Important Considerations

### 1. **Mac Sleep/Hibernation**
```bash
# Prevent Mac from sleeping (optional)
sudo pmset -c sleep 0
sudo pmset -c displaysleep 10  # Display can sleep, but not system

# Or use caffeinate to keep awake
caffeinate -s &  # Prevent system sleep
```

### 2. **Network Connectivity**
- **Mac**: Ensure stable internet for Oracle Cloud uploads
- **Oracle VM**: Free tier VMs can be stopped by Oracle if idle too long
- **Solution**: Keep some activity or upgrade to paid tier

### 3. **Resource Management**
```bash
# Monitor Mac resources
top -pid $(pgrep -f mac_screenshot_daemon)

# Monitor Oracle VM resources  
top
htop
free -h
df -h
```

### 4. **Log Rotation**
```bash
# Mac log rotation (add to crontab)
echo "0 0 * * * /usr/bin/find /tmp -name '*screenshot*.log' -size +100M -delete" | crontab -

# Oracle VM log rotation
sudo logrotate /etc/logrotate.conf
```

### 5. **Error Recovery**
Both services are designed to restart automatically on errors, but monitor logs:

```bash
# Mac monitoring
tail -f /tmp/screenshot_daemon.log

# Oracle VM monitoring  
sudo journalctl -u screenshot-watcher -f
```

### 6. **Cost Monitoring**
- **OpenAI**: ~$0.01-0.03 per screenshot
- **Oracle Cloud**: Free tier limits (monitor usage)
- **Bandwidth**: Oracle gives 10TB/month free

### 7. **Security Considerations**
- **API Keys**: Stored in environment variables, not code
- **SSH**: Use key-based auth, consider fail2ban
- **Network**: Oracle VM has public IP, ensure firewall rules

## 🚀 Recommended Setup Process

### Quick Start (Testing)
```bash
# Mac
nohup python3 mac_screenshot_daemon.py start &

# Oracle VM (in screen session)
screen -S watcher
export OPENAI_API_KEY=your-key
python3 screenshot_watcher.py
# Ctrl+A, D to detach
```

### Production Setup (Long-term)
```bash
# Mac: LaunchAgent for auto-start
launchctl load ~/Library/LaunchAgents/com.finesse.screenshot.plist

# Oracle VM: Systemd service for auto-start
sudo systemctl enable screenshot-watcher
sudo systemctl start screenshot-watcher
```

## 📊 Monitoring Dashboard

### Daily Health Check
```bash
# Mac
python3 mac_screenshot_daemon.py status
ls -la /tmp/screenshot*.log

# Oracle VM  
sudo systemctl status screenshot-watcher
ls -la /tmp/processed_screenshots/
```

### Weekly Maintenance
- Check log file sizes
- Monitor Oracle Cloud storage usage
- Check OpenAI API usage
- Verify both services are running

---

## 🎯 TL;DR - Quick Setup

**Mac:**
```bash
nohup python3 mac_screenshot_daemon.py start > /tmp/mac_daemon.log 2>&1 &
```

**Oracle VM:**
```bash
screen -S watcher
export OPENAI_API_KEY=your-key
python3 screenshot_watcher.py
# Ctrl+A, D
```

Both will now run continuously in the background! 🚀
