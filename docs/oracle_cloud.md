# Oracle Cloud Object Storage Setup Guide

## 1. Oracle Cloud Account Setup

1. **Create Oracle Cloud Free Tier Account**
   - Visit: https://www.oracle.com/cloud/free/
   - Sign up for free tier account
   - Complete verification process

2. **Create Object Storage Bucket**
   - Login to Oracle Cloud Console
   - Navigate to: Storage → Object Storage & Archive Storage → Buckets
   - Click "Create Bucket"
   - Bucket Name: `screenshot-bucket`
   - Storage Tier: Standard
   - Object Events: Disabled (or enable if you want real-time notifications)
   - Encryption: Oracle Managed Keys
   - Click "Create"

## 2. IAM Configuration

1. **Create API Key for Mac Client**
   - Navigate to: Identity & Security → Users
   - Click on your username
   - Go to "API Keys" section
   - Click "Add API Key"
   - Choose "Generate API Key Pair"
   - Download both private key and public key
   - Copy the configuration preview

2. **Create Dynamic Group and Policies for VM**
   - Navigate to: Identity & Security → Dynamic Groups
   - Create dynamic group with matching rule:
     ```
     ALL {instance.compartment.id = 'your-compartment-ocid'}
     ```
   - Navigate to: Identity & Security → Policies
   - Create policy with statements:
     ```
     Allow dynamic-group screenshot-group to manage objects in compartment id your-compartment-ocid
     Allow dynamic-group screenshot-group to manage buckets in compartment id your-compartment-ocid
     ```

## 3. Oracle Cloud VM Setup

1. **Create Compute Instance**
   - Navigate to: Compute → Instances
   - Click "Create Instance"
   - Name: `screenshot-processor`
   - Image: Oracle Linux 8 or Ubuntu 20.04 LTS
   - Shape: VM.Standard.E2.1.Micro (Always Free eligible)
   - Networking: Create in public subnet with public IP
   - SSH Keys: Add your public SSH key
   - Click "Create"

2. **Configure VM Security**
   - Navigate to: Networking → Virtual Cloud Networks
   - Click on your VCN → Security Lists → Default Security List
   - Add Ingress Rules (if needed for debugging):
     - Source: 0.0.0.0/0
     - Port: 22 (SSH)

## 4. Mac Configuration

1. **Install Oracle CLI**
   ```bash
   # Install using pip
   pip3 install oci-cli
   
   # Or using homebrew
   brew install oci-cli
   ```

2. **Configure Oracle CLI**
   ```bash
   # Create config directory
   mkdir -p ~/.oci
   
   # Create config file
   cat > ~/.oci/config << EOF
   [DEFAULT]
   user=your-user-ocid
   fingerprint=your-api-key-fingerprint
   tenancy=your-tenancy-ocid
   region=your-region
   key_file=~/.oci/oci_api_key.pem
   EOF
   
   # Copy your private key to the config directory
   cp /path/to/downloaded/private/key ~/.oci/oci_api_key.pem
   chmod 600 ~/.oci/oci_api_key.pem
   ```

3. **Install Python Dependencies**
   ```bash
   pip3 install oci
   ```

## 5. VM Configuration

1. **SSH into VM**
   ```bash
   ssh -i ~/.ssh/your-key opc@your-vm-public-ip
   ```

2. **Install Python and Dependencies**
   ```bash
   # For Oracle Linux 8
   sudo dnf install python3 python3-pip -y
   
   # For Ubuntu
   sudo apt update && sudo apt install python3 python3-pip -y
   
   # Install required packages
   pip3 install oci openai requests pillow python-telegram-bot
   ```

3. **Configure Instance Principal Authentication**
   - The VM will use Instance Principal authentication (no API keys needed)
   - This is automatically configured when the VM is in the dynamic group

## 6. Bucket Access URLs

- **Bucket Console URL**: https://cloud.oracle.com/object-storage/buckets/your-region/your-namespace/screenshot-bucket
- **API Endpoint**: https://objectstorage.your-region.oraclecloud.com

## Environment Variables to Set

### On Mac (for uploader script):
```bash
export OCI_CONFIG_FILE=~/.oci/config
export OCI_CONFIG_PROFILE=DEFAULT
```

### On Oracle VM (for watcher script):
```bash
export OPENAI_API_KEY=your-openai-api-key
export TELEGRAM_BOT_TOKEN=your-telegram-bot-token  # Optional
export TELEGRAM_CHAT_ID=your-chat-id              # Optional
export NTFY_TOPIC=your-ntfy-topic                 # Optional
```

## Testing Connection

Test your Oracle Cloud connection:

```python
import oci

# On Mac
config = oci.config.from_file("~/.oci/config", "DEFAULT")
object_storage = oci.object_storage.ObjectStorageClient(config)

# On VM (using instance principal)
signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)

# Test connection
namespace = object_storage.get_namespace().data
print(f"Connected! Namespace: {namespace}")
```
