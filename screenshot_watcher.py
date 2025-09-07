#!/usr/bin/env python3
"""
Screenshot Watcher for Oracle Cloud VM
Polls Oracle Cloud Object Storage for new screenshots, processes them with OpenAI Vision API,
and sends results to phone via ntfy or Telegram
"""

import os
import sys
import time
import json
import base64
import logging
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
import oci
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/screenshot_watcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NotificationSender:
    """Handles sending notifications via different methods"""
    
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.ntfy_topic = os.getenv('NTFY_TOPIC')
        
    def send_via_telegram(self, message: str, filename: str = None, file_content: str = None):
        """Send message via Telegram bot"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("Telegram credentials not configured")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            
            # Send text message
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                logger.info("Message sent via Telegram")
                
                # Send file if provided
                if filename and file_content:
                    self._send_telegram_document(filename, file_content)
                
                return True
            else:
                logger.error(f"Telegram API error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def _send_telegram_document(self, filename: str, content: str):
        """Send file as document via Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendDocument"
            
            files = {
                'document': (filename, content.encode('utf-8'), 'text/plain')
            }
            
            data = {
                'chat_id': self.telegram_chat_id,
                'caption': f'📝 Extracted Python code: `{filename}`'
            }
            
            response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                logger.info(f"File {filename} sent via Telegram")
            else:
                logger.error(f"Error sending Telegram file: {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending Telegram document: {e}")
    
    def send_via_ntfy(self, message: str, filename: str = None, file_content: str = None):
        """Send message via ntfy.sh"""
        if not self.ntfy_topic:
            logger.warning("ntfy topic not configured")
            return False
            
        try:
            url = f"https://ntfy.sh/{self.ntfy_topic}"
            
            # Send main notification
            headers = {
                'Title': '🖥️ Screenshot Code Extracted',
                'Priority': 'default',
                'Tags': 'computer,code'
            }
            
            response = requests.post(url, data=message.encode('utf-8'), headers=headers)
            
            if response.status_code == 200:
                logger.info("Message sent via ntfy")
                
                # Send file content as separate message if provided
                if filename and file_content:
                    file_headers = {
                        'Title': f'📄 {filename}',
                        'Priority': 'low',
                        'Tags': 'file,python'
                    }
                    
                    # Truncate if too long for ntfy
                    truncated_content = file_content[:2000]
                    if len(file_content) > 2000:
                        truncated_content += "\n\n... (content truncated, see Telegram for full file)"
                    
                    requests.post(url, data=f"```python\n{truncated_content}\n```".encode('utf-8'), headers=file_headers)
                
                return True
            else:
                logger.error(f"ntfy error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending ntfy message: {e}")
            return False
    
    def send_notification(self, message: str, filename: str = None, file_content: str = None):
        """Send notification via all configured methods"""
        success = False
        
        if self.telegram_bot_token and self.telegram_chat_id:
            success |= self.send_via_telegram(message, filename, file_content)
        
        if self.ntfy_topic:
            success |= self.send_via_ntfy(message, filename, file_content)
        
        if not success:
            logger.warning("No notification methods configured or all failed")
        
        return success

class ScreenshotWatcher:
    """Main class for watching and processing screenshots"""
    
    def __init__(self):
        # Initialize Oracle Cloud client with Instance Principal
        try:
            signer = InstancePrincipalsSecurityTokenSigner()
            self.object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
            self.namespace = self.object_storage.get_namespace().data
            logger.info(f"Initialized Oracle Cloud client with namespace: {self.namespace}")
        except Exception as e:
            logger.error(f"Failed to initialize Oracle Cloud client: {e}")
            sys.exit(1)
        
        # Configuration
        self.bucket_name = "screenshot-bucket"
        self.processed_dir = Path("/tmp/processed_screenshots")
        self.processed_dir.mkdir(exist_ok=True)
        
        # Keep track of processed files
        self.processed_files = set()
        self.state_file = Path("/tmp/processed_screenshots.json")
        self._load_processed_state()
        
        # Initialize OpenAI
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            sys.exit(1)
        
        # Initialize notification sender
        self.notifier = NotificationSender()
        
        logger.info("Screenshot watcher initialized successfully")
    
    def _load_processed_state(self):
        """Load the list of already processed files"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.processed_files = set(data.get('processed_files', []))
                    logger.info(f"Loaded {len(self.processed_files)} processed files from state")
        except Exception as e:
            logger.warning(f"Could not load processed state: {e}")
            self.processed_files = set()
    
    def _save_processed_state(self):
        """Save the list of processed files"""
        try:
            data = {
                'processed_files': list(self.processed_files),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save processed state: {e}")
    
    def get_new_screenshots(self) -> List[str]:
        """Get list of new screenshots from Oracle Cloud bucket"""
        try:
            # List objects in screenshots/ prefix
            list_objects_response = self.object_storage.list_objects(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                prefix="screenshots/",
                fields="name,timeCreated"
            )
            
            new_screenshots = []
            
            for obj in list_objects_response.data.objects:
                object_name = obj.name
                
                # Skip if already processed
                if object_name in self.processed_files:
                    continue
                
                # Only process PNG files
                if not object_name.lower().endswith('.png'):
                    continue
                
                new_screenshots.append(object_name)
            
            logger.info(f"Found {len(new_screenshots)} new screenshots")
            return new_screenshots
            
        except Exception as e:
            logger.error(f"Error listing objects: {e}")
            return []
    
    def download_screenshot(self, object_name: str) -> Optional[bytes]:
        """Download screenshot from Oracle Cloud bucket"""
        try:
            get_object_response = self.object_storage.get_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            
            image_data = get_object_response.data.content
            logger.info(f"Downloaded {object_name}, size: {len(image_data)} bytes")
            return image_data
            
        except Exception as e:
            logger.error(f"Error downloading {object_name}: {e}")
            return None
    
    def extract_code_with_openai(self, image_data: bytes) -> Optional[str]:
        """Extract Python code from screenshot using OpenAI Vision API"""
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare the request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai.api_key}"
            }
            
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                        {
                            "type": "text",
                            "text": "You are a Python problem-solving assistant. Your task is to analyze screenshots that may contain: A problem statement, Python code, Test cases (sometimes failing). Always produce corrected or new Python code that solves the problem and makes all tests pass. If the screenshot contains only a problem, provide complete Python code that solves it. If it contains failing test cases and code, carefully read them and return a fixed version of the code that passes the tests. Keep your answer concise: only output the Python code unless brief clarification is necessary. If there's no Python-related content visible, return 'NO_CODE_FOUND'."
                        },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 2000
            }
            
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                extracted_text = result['choices'][0]['message']['content'].strip()
                
                if extracted_text == 'NO_CODE_FOUND' or not extracted_text:
                    logger.info("No Python code found in screenshot")
                    return None
                
                logger.info("Successfully extracted code from screenshot")
                return extracted_text
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting code with OpenAI: {e}")
            return None
    
    def save_extracted_code(self, code: str, original_filename: str) -> str:
        """Save extracted code to a .py file"""
        try:
            # Generate filename based on original screenshot name
            base_name = Path(original_filename).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            py_filename = f"{base_name}_{timestamp}.py"
            py_filepath = self.processed_dir / py_filename
            
            # Add header comment
            header = f"""# Extracted from screenshot: {original_filename}
# Processed at: {datetime.now().isoformat()}
# Auto-generated by Screenshot Watcher

"""
            
            with open(py_filepath, 'w', encoding='utf-8') as f:
                f.write(header + code)
            
            logger.info(f"Saved extracted code to: {py_filename}")
            return py_filename
            
        except Exception as e:
            logger.error(f"Error saving extracted code: {e}")
            return None
    
    def process_screenshot(self, object_name: str):
        """Process a single screenshot"""
        logger.info(f"Processing screenshot: {object_name}")
        
        try:
            # Download screenshot
            image_data = self.download_screenshot(object_name)
            if not image_data:
                return False
            
            # Extract code using OpenAI
            extracted_code = self.extract_code_with_openai(image_data)
            if not extracted_code:
                logger.info(f"No code found in {object_name}")
                # Still mark as processed to avoid reprocessing
                self.processed_files.add(object_name)
                self._save_processed_state()
                return True
            
            # Save extracted code
            py_filename = self.save_extracted_code(extracted_code, object_name)
            if not py_filename:
                return False
            
            # Send notification
            message = f"🐍 **Python Code Extracted!**\n\n📸 From: `{object_name}`\n📝 Saved as: `{py_filename}`\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            self.notifier.send_notification(message, py_filename, extracted_code)
            
            # Mark as processed
            self.processed_files.add(object_name)
            self._save_processed_state()
            
            logger.info(f"Successfully processed {object_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing {object_name}: {e}")
            return False
    
    def mark_existing_as_processed(self):
        """Mark all existing screenshots as processed (skip old screenshots)"""
        try:
            response = self.object_storage.list_objects(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                prefix="screenshots/",
                fields="name"
            )
            
            existing_count = 0
            for obj in response.data.objects:
                if obj.name.lower().endswith('.png'):
                    self.processed_files.add(obj.name)
                    existing_count += 1
            
            self._save_processed_state()
            logger.info(f"Marked {existing_count} existing screenshots as processed (will skip them)")
            
        except Exception as e:
            logger.error(f"Error marking existing screenshots: {e}")

    def run_watcher(self, poll_interval: int = 30, skip_existing: bool = True):
        """Run the main watcher loop"""
        if skip_existing:
            logger.info("🔄 Marking existing screenshots as processed (will only process NEW screenshots)")
            self.mark_existing_as_processed()
        
        logger.info(f"Starting screenshot watcher (polling every {poll_interval} seconds)")
        logger.info("📸 Waiting for NEW screenshots to be uploaded...")
        
        while True:
            try:
                # Get new screenshots
                new_screenshots = self.get_new_screenshots()
                
                # Process each new screenshot
                for screenshot in new_screenshots:
                    self.process_screenshot(screenshot)
                    # Small delay between processing
                    time.sleep(2)
                
                if not new_screenshots:
                    logger.debug("No new screenshots found")
                
                # Wait for next poll
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Screenshot watcher stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

def main():
    """Main function"""
    try:
        watcher = ScreenshotWatcher()
        watcher.run_watcher(poll_interval=30)  # Poll every 30 seconds
    except Exception as e:
        logger.error(f"Failed to start screenshot watcher: {e}")
        print("Make sure all environment variables are set and Oracle Cloud is configured.")

if __name__ == "__main__":
    main()
