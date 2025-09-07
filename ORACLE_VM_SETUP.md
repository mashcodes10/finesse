# ☁️ Oracle VM Setup for OpenAI Processing

## 📋 Prerequisites

Before starting, make sure you have:
- ✅ Oracle Cloud Free Tier VM running (from previous setup)
- ✅ OpenAI API key with GPT-4 Vision access
- ✅ SSH access to your Oracle VM
- ✅ Screenshots uploading to Oracle Cloud bucket (from Mac)

## 🔑 Get Your OpenAI API Key

1. **Visit**: https://platform.openai.com/api-keys
2. **Sign in** to your OpenAI account
3. **Create new secret key** → Copy and save it
4. **Check model access**: Make sure you have GPT-4 Vision access

## 🖥️ Step 1: Connect to Your Oracle VM

```bash
# SSH to your Oracle VM (replace with your VM's public IP)
ssh -i ~/.ssh/your-key opc@your-vm-public-ip
```

## 📦 Step 2: Install Dependencies on Oracle VM

```bash
# Update system packages
sudo dnf update -y  # For Oracle Linux
# OR for Ubuntu: sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo dnf install python3 python3-pip git -y
# OR for Ubuntu: sudo apt install python3 python3-pip git -y

# Install required Python packages
pip3 install --user oci openai requests pillow python-telegram-bot

# Add pip user bin to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## 📁 Step 3: Upload Scripts to Oracle VM

**Option A: Clone from your repository (if you've pushed to GitHub)**
```bash
git clone your-repo-url finesse
cd finesse
```

**Option B: Copy files manually via SCP**
```bash
# Run this from your Mac terminal
scp -i ~/.ssh/your-key /Users/md.mashiurrahmankhan/Downloads/projects/finesse/screenshot_watcher.py opc@your-vm-ip:~/
scp -i ~/.ssh/your-key /Users/md.mashiurrahmankhan/Downloads/projects/finesse/requirements_vm.txt opc@your-vm-ip:~/
```

## 🔧 Step 4: Configure Environment Variables

```bash
# Create environment file
cat > ~/.env << EOF
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here

# Notification Configuration (choose one or both)
TELEGRAM_BOT_TOKEN=your-telegram-bot-token  # Optional
TELEGRAM_CHAT_ID=your-telegram-chat-id      # Optional
NTFY_TOPIC=your-unique-ntfy-topic          # Optional
EOF

# Load environment variables
echo 'source ~/.env' >> ~/.bashrc
source ~/.bashrc
```

## 🔄 Step 5: Test OpenAI Connection

```bash
python3 -c "
import openai
import os

# Set API key
openai.api_key = os.getenv('OPENAI_API_KEY')

if not openai.api_key:
    print('❌ OPENAI_API_KEY not set')
    exit(1)

try:
    # Test API connection
    import requests
    headers = {'Authorization': f'Bearer {openai.api_key}'}
    response = requests.get('https://api.openai.com/v1/models', headers=headers)
    
    if response.status_code == 200:
        print('✅ OpenAI API connection successful!')
        models = response.json()
        
        # Check for GPT-4 Vision
        vision_models = [m for m in models.get('data', []) if 'vision' in m.get('id', '')]
        if vision_models:
            print('✅ GPT-4 Vision access confirmed!')
        else:
            print('⚠️ GPT-4 Vision model not found in your account')
    else:
        print(f'❌ API Error: {response.status_code}')
        
except Exception as e:
    print(f'❌ Connection test failed: {e}')
"
```

## 🖥️ Step 6: Test Oracle Cloud Access (Instance Principal)

```bash
python3 -c "
import oci
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner

try:
    # Use Instance Principal authentication
    signer = InstancePrincipalsSecurityTokenSigner()
    object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
    
    # Test connection
    namespace = object_storage.get_namespace().data
    print(f'✅ Oracle Cloud connected! Namespace: {namespace}')
    
    # Test bucket access
    response = object_storage.list_objects(
        namespace_name=namespace,
        bucket_name='screenshot-bucket',
        prefix='screenshots/',
        limit=5
    )
    
    print(f'✅ Bucket access successful! Found {len(response.data.objects)} screenshots')
    for obj in response.data.objects:
        print(f'   📷 {obj.name}')
        
except Exception as e:
    print(f'❌ Oracle Cloud connection failed: {e}')
    print('Make sure your VM is in the correct dynamic group with bucket permissions')
"
```

## 🔄 Step 7: Run the Screenshot Watcher

```bash
# Test run (foreground)
python3 screenshot_watcher.py

# Or run as background service
nohup python3 screenshot_watcher.py > /tmp/watcher.log 2>&1 &
```

## 📊 Step 8: Monitor the System

```bash
# Check watcher logs
tail -f /tmp/watcher.log

# Check system resources
htop  # or top

# Check running processes
ps aux | grep python
```

## 🔧 Step 9: Create Systemd Service (Auto-start)

```bash
# Create service file
sudo tee /etc/systemd/system/screenshot-watcher.service > /dev/null << EOF
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

# Environment variables
EnvironmentFile=$HOME/.env

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable screenshot-watcher
sudo systemctl start screenshot-watcher

# Check service status
sudo systemctl status screenshot-watcher
```

## 🧪 Testing the Complete Pipeline

1. **Take a screenshot on Mac** (cursor trigger)
2. **Check Oracle Cloud bucket** for new screenshots
3. **Monitor VM logs** for processing activity
4. **Verify OpenAI processing** in logs
5. **Check for notifications** (if configured)

## 🔍 Troubleshooting

### OpenAI API Issues
```bash
# Check API key
echo $OPENAI_API_KEY

# Test manual API call
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Oracle Cloud Issues
```bash
# Check instance principal
oci-metadata --get /instance

# Verify dynamic group membership
# (Check Oracle Cloud Console → Identity & Security → Dynamic Groups)
```

### Service Issues
```bash
# Check service logs
sudo journalctl -u screenshot-watcher -f

# Restart service
sudo systemctl restart screenshot-watcher
```

## 📈 Performance Monitoring

```bash
# Monitor CPU/Memory usage
htop

# Check API usage
# Monitor OpenAI dashboard: https://platform.openai.com/usage

# Check Oracle Cloud costs
# Monitor Oracle Cloud Console billing
```

## 🎯 Expected Behavior

Once everything is set up correctly:

1. **📸 Mac takes screenshot** → Uploads to Oracle Cloud
2. **☁️ Oracle VM detects new screenshot** → Downloads it  
3. **🤖 OpenAI processes image** → Extracts Python code
4. **💾 Code saved as .py file** → Formatted and clean
5. **📱 Notification sent** → Code delivered to your phone

---

**🚀 Ready to start? Let's begin with Step 1 - connecting to your Oracle VM!**
