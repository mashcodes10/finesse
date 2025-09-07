# Complete Deployment Guide

This guide provides step-by-step instructions to deploy the entire screenshot analysis pipeline.

## Overview

The system consists of:
1. **Mac Script**: Takes screenshots every 5 minutes and uploads to Oracle Cloud
2. **Oracle Cloud**: Object Storage bucket to store screenshots
3. **Oracle VM**: Watcher script that processes screenshots with OpenAI Vision API
4. **Phone Notifications**: Delivers extracted Python code via ntfy.sh or Telegram

## Prerequisites

- Mac with macOS 10.14+ 
- Oracle Cloud Free Tier account
- OpenAI API key
- Phone with ntfy app or Telegram

## Step 1: Oracle Cloud Setup

### 1.1 Create Oracle Cloud Account
1. Visit https://www.oracle.com/cloud/free/
2. Sign up for free tier account
3. Complete email verification

### 1.2 Create Object Storage Bucket
1. Login to Oracle Cloud Console
2. Navigate to: **Storage → Object Storage & Archive Storage → Buckets**
3. Click **"Create Bucket"**
4. Settings:
   - **Name**: `screenshot-bucket`
   - **Storage Tier**: Standard
   - **Encryption**: Oracle Managed Keys
5. Click **"Create"**

### 1.3 Set Up API Access
1. Navigate to: **Identity & Security → Users**
2. Click your username
3. Go to **"API Keys"** section
4. Click **"Add API Key"**
5. Choose **"Generate API Key Pair"**
6. Download both private and public keys
7. Copy the configuration preview

### 1.4 Create Oracle VM
1. Navigate to: **Compute → Instances**
2. Click **"Create Instance"**
3. Settings:
   - **Name**: `screenshot-processor`
   - **Image**: Oracle Linux 8 or Ubuntu 20.04 LTS
   - **Shape**: VM.Standard.E2.1.Micro (Always Free)
   - **Networking**: Public subnet with public IP
   - **SSH Keys**: Upload your SSH public key
4. Click **"Create"**

### 1.5 Configure IAM for VM
1. Navigate to: **Identity & Security → Dynamic Groups**
2. Create dynamic group with rule:
   ```
   ALL {instance.compartment.id = 'your-compartment-ocid'}
   ```
3. Navigate to: **Identity & Security → Policies**
4. Create policy with statements:
   ```
   Allow dynamic-group screenshot-group to manage objects in compartment id your-compartment-ocid
   Allow dynamic-group screenshot-group to manage buckets in compartment id your-compartment-ocid
   ```

## Step 2: Mac Setup

### 2.1 Clone Repository
```bash
cd ~/Downloads
git clone <your-repo-url> finesse
cd finesse
```

### 2.2 Install Dependencies
```bash
chmod +x install_mac.sh
./install_mac.sh
```

### 2.3 Configure Oracle CLI
```bash
mkdir -p ~/.oci
# Copy your downloaded private key to ~/.oci/oci_api_key.pem
cp ~/Downloads/your-private-key.pem ~/.oci/oci_api_key.pem
chmod 600 ~/.oci/oci_api_key.pem

# Create config file (replace with your values)
cat > ~/.oci/config << EOF
[DEFAULT]
user=ocid1.user.oc1..your-user-ocid
fingerprint=your-fingerprint
tenancy=ocid1.tenancy.oc1..your-tenancy-ocid
region=us-ashburn-1
key_file=~/.oci/oci_api_key.pem
EOF
```

### 2.4 Test Oracle Connection
```bash
python3 -c "
import oci
config = oci.config.from_file('~/.oci/config', 'DEFAULT')
client = oci.object_storage.ObjectStorageClient(config)
print('✅ Oracle Cloud connection successful!')
print('Namespace:', client.get_namespace().data)
"
```

### 2.5 Start Screenshot Uploader
```bash
# Test run
python3 mac_screenshot_uploader.py

# Run in background
nohup python3 mac_screenshot_uploader.py > /tmp/screenshot_uploader.log 2>&1 &
```

### 2.6 Set Up Auto-Start (Optional)
```bash
# Add to crontab for auto-start on boot
(crontab -l 2>/dev/null; echo "@reboot cd $(pwd) && python3 mac_screenshot_uploader.py >> /tmp/screenshot_uploader.log 2>&1") | crontab -
```

## Step 3: Oracle VM Setup

### 3.1 SSH to Oracle VM
```bash
ssh -i ~/.ssh/your-key opc@your-vm-public-ip
```

### 3.2 Clone Repository and Install
```bash
git clone <your-repo-url> finesse
cd finesse
chmod +x install_vm.sh
./install_vm.sh
```

### 3.3 Configure Environment Variables
```bash
# Edit the systemd service file
sudo nano /etc/systemd/system/screenshot-watcher.service

# Update these lines with your actual values:
Environment=OPENAI_API_KEY=sk-your-openai-api-key
Environment=TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
Environment=TELEGRAM_CHAT_ID=your-chat-id
Environment=NTFY_TOPIC=your-unique-ntfy-topic
```

### 3.4 Start the Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable screenshot-watcher
sudo systemctl start screenshot-watcher
```

### 3.5 Verify Service Status
```bash
sudo systemctl status screenshot-watcher
sudo journalctl -u screenshot-watcher -f
```

## Step 4: Phone Notification Setup

### Option A: ntfy.sh (Recommended)

1. **Install ntfy app**:
   - Android: Google Play Store
   - iOS: App Store

2. **Choose unique topic**: `yourname-screenshots-123456`

3. **Subscribe in app**:
   - Open ntfy app
   - Tap "+" button
   - Enter your topic
   - Tap "Subscribe"

4. **Test notification**:
   ```bash
   curl -d "Test from Oracle VM" ntfy.sh/yourname-screenshots-123456
   ```

### Option B: Telegram Bot

1. **Create bot**:
   - Message @BotFather on Telegram
   - Send `/newbot`
   - Follow prompts
   - Save bot token

2. **Get chat ID**:
   - Start chat with your bot
   - Send any message
   - Visit: `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`
   - Find chat ID in response

3. **Test notification**:
   ```bash
   curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
     -H "Content-Type: application/json" \
     -d "{\"chat_id\": \"${CHAT_ID}\", \"text\": \"Test from Oracle VM\"}"
   ```

## Step 5: Testing End-to-End

### 5.1 Test Screenshot Upload
1. Check if Mac is taking screenshots:
   ```bash
   tail -f /tmp/screenshot_uploader.log
   ```

2. Verify uploads in Oracle Cloud Console:
   - Go to Object Storage → screenshot-bucket
   - Look for files in `screenshots/` folder

### 5.2 Test Code Extraction
1. Create a simple Python script on your screen
2. Wait for screenshot to be taken and uploaded
3. Check Oracle VM logs:
   ```bash
   sudo journalctl -u screenshot-watcher -f
   ```
4. Verify notification received on phone

### 5.3 Full Pipeline Test
1. Open a Python IDE or text editor
2. Write some Python code (e.g., a simple function)
3. Wait 5 minutes for screenshot
4. Check phone for notification with extracted code

## Troubleshooting

### Mac Issues
- **Permission denied for screenshots**: Grant Terminal/Python screen recording permission in System Preferences → Security & Privacy → Privacy → Screen Recording
- **Oracle upload fails**: Check API key configuration and internet connection
- **High CPU usage**: Screenshots use minimal resources, check for other processes

### Oracle VM Issues
- **Service won't start**: Check environment variables and Python dependencies
- **OpenAI API errors**: Verify API key and check quota/billing
- **Bucket access denied**: Verify IAM policies and dynamic group configuration

### Notification Issues
- **ntfy not working**: Check topic name and internet connectivity
- **Telegram not working**: Verify bot token and chat ID
- **No notifications**: Check Oracle VM internet access and API quotas

### General Issues
- **No code extracted**: Ensure Python code is clearly visible and readable in screenshots
- **False positives**: OpenAI might extract code-like text; this is expected behavior
- **Performance**: Free tier resources are limited; consider upgrading for heavy usage

## Monitoring and Maintenance

### Log Files
- **Mac**: `/tmp/screenshot_uploader.log`
- **Oracle VM**: `sudo journalctl -u screenshot-watcher`

### Regular Maintenance
1. **Clean up old screenshots** (Oracle Cloud storage has costs beyond free tier)
2. **Monitor OpenAI API usage** (check usage dashboard)
3. **Update dependencies** periodically for security
4. **Check Oracle Cloud free tier limits**

### Service Management
```bash
# Oracle VM service commands
sudo systemctl status screenshot-watcher    # Check status
sudo systemctl restart screenshot-watcher   # Restart service
sudo systemctl stop screenshot-watcher      # Stop service
sudo systemctl start screenshot-watcher     # Start service
```

## Security Considerations

1. **API Keys**: Store securely, never commit to version control
2. **Oracle Cloud**: Use principle of least privilege for IAM policies
3. **SSH Access**: Use key-based authentication only
4. **Notifications**: ntfy topics are public; use unique, hard-to-guess names
5. **Screenshots**: May contain sensitive information; ensure secure storage and processing

## Cost Optimization

1. **Oracle Cloud Free Tier Limits**:
   - 20GB Object Storage
   - VM: 1/8 OCPU, 1GB RAM
   - 10TB outbound data transfer/month

2. **OpenAI API Costs**:
   - GPT-4 Vision: ~$0.01-0.03 per image
   - Monitor usage in OpenAI dashboard

3. **Optimization Tips**:
   - Clean up old screenshots regularly
   - Use image compression if needed
   - Implement smart screenshot detection (only when screen changes)

---

🎉 **Congratulations!** Your automated screenshot analysis pipeline is now ready. You should start receiving Python code extractions on your phone whenever you write code on your Mac screen.
