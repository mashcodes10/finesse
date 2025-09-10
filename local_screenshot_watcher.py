#!/usr/bin/env python3
"""
Local Screenshot Watcher - Mac Version
Processes screenshots using Mac Oracle CLI config instead of Instance Principal
"""

import os
import sys
import time
import json
import base64
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import oci
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/local_watcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LocalScreenshotWatcher:
    """Local version of screenshot watcher for Mac testing"""
    
    def __init__(self):
        # Initialize Oracle Cloud client with local config
        try:
            self.config = oci.config.from_file("~/.oci/config", "DEFAULT")
            self.object_storage = oci.object_storage.ObjectStorageClient(self.config)
            self.namespace = self.object_storage.get_namespace().data
            logger.info(f"Oracle Cloud connected. Namespace: {self.namespace}")
        except Exception as e:
            logger.error(f"Failed to initialize Oracle Cloud: {e}")
            sys.exit(1)
        
        # Configuration
        self.bucket_name = "screenshot-bucket"
        self.processed_dir = Path("/tmp/processed_screenshots")
        self.processed_dir.mkdir(exist_ok=True)
        
        # State management
        self.processed_files = set()
        self.state_file = Path("/tmp/local_processed_state.json")
        self._load_processed_state()
        
        # OpenAI setup
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            sys.exit(1)
        
        logger.info("Local screenshot watcher initialized successfully")

    def _load_processed_state(self):
        """Load processed files state"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.processed_files = set(data.get('processed_files', []))
                    logger.info(f"Loaded {len(self.processed_files)} processed files from state")
        except Exception as e:
            logger.warning(f"Could not load state: {e}")
            self.processed_files = set()

    def _save_processed_state(self):
        """Save processed files state"""
        try:
            data = {
                'processed_files': list(self.processed_files),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save state: {e}")

    def get_new_screenshots(self) -> List[str]:
        """Get new screenshots from bucket"""
        try:
            response = self.object_storage.list_objects(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                prefix="screenshots/",
                fields="name,timeCreated"
            )
            
            new_screenshots = []
            for obj in response.data.objects:
                if obj.name not in self.processed_files and obj.name.lower().endswith('.png'):
                    new_screenshots.append(obj.name)
            
            logger.info(f"Found {len(new_screenshots)} new screenshots to process")
            return new_screenshots
            
        except Exception as e:
            logger.error(f"Error listing objects: {e}")
            return []

    def download_screenshot(self, object_name: str) -> Optional[bytes]:
        """Download screenshot from bucket"""
        try:
            response = self.object_storage.get_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            
            image_data = response.data.content
            logger.info(f"Downloaded {object_name}, size: {len(image_data)} bytes")
            return image_data
            
        except Exception as e:
            logger.error(f"Error downloading {object_name}: {e}")
            return None

    def extract_code_with_openai(self, image_data: bytes) -> Optional[str]:
        """Extract Python code using OpenAI Vision API"""
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
                usage = result.get('usage', {})
                
                logger.info(f"OpenAI processing successful. Tokens: {usage.get('total_tokens', 'unknown')}")
                
                if extracted_text == 'NO_CODE_FOUND' or not extracted_text:
                    logger.info("No Python code found in screenshot")
                    return None
                
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
            base_name = Path(original_filename).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            py_filename = f"{base_name}_{timestamp}.py"
            py_filepath = self.processed_dir / py_filename
            
            header = f"""# Extracted from screenshot: {original_filename}
# Processed at: {datetime.now().isoformat()}
# Local Screenshot Watcher - Mac Version

"""
            
            with open(py_filepath, 'w', encoding='utf-8') as f:
                f.write(header + code)
            
            logger.info(f"Saved extracted code to: {py_filename}")
            return py_filename
            
        except Exception as e:
            logger.error(f"Error saving extracted code: {e}")
            return None

    def send_notification(self, message: str, filename: str, code: str):
        """Send notification (local version just logs)"""
        logger.info("📱 NOTIFICATION READY:")
        logger.info(f"   Message: {message}")
        logger.info(f"   File: {filename}")
        logger.info(f"   Code preview: {code[:200]}...")
        
        print("\n" + "="*60)
        print("📱 NOTIFICATION - EXTRACTED PYTHON CODE")
        print("="*60)
        print(f"📸 Screenshot: {message}")
        print(f"📝 File: {filename}")
        print(f"🐍 Code:")
        print("-" * 40)
        print(code)
        print("-" * 40)
        print("="*60)

    def process_screenshot(self, object_name: str):
        """Process a single screenshot"""
        logger.info(f"🔄 Processing screenshot: {object_name}")
        
        try:
            # Download
            image_data = self.download_screenshot(object_name)
            if not image_data:
                return False
            
            # Extract code
            extracted_code = self.extract_code_with_openai(image_data)
            if not extracted_code:
                logger.info(f"No code found in {object_name}")
                self.processed_files.add(object_name)
                self._save_processed_state()
                return True
            
            # Save code
            py_filename = self.save_extracted_code(extracted_code, object_name)
            if not py_filename:
                return False
            
            # Send notification
            message = f"From {object_name}"
            self.send_notification(message, py_filename, extracted_code)
            
            # Mark as processed
            self.processed_files.add(object_name)
            self._save_processed_state()
            
            logger.info(f"✅ Successfully processed {object_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing {object_name}: {e}")
            return False

    def run_watcher(self, process_all: bool = True):
        """Run the watcher - process existing screenshots"""
        logger.info("🚀 Starting local screenshot watcher")
        
        try:
            new_screenshots = self.get_new_screenshots()
            
            if not new_screenshots:
                logger.info("✅ No new screenshots to process")
                return
            
            logger.info(f"📋 Processing {len(new_screenshots)} screenshots...")
            
            for i, screenshot in enumerate(new_screenshots, 1):
                logger.info(f"📸 [{i}/{len(new_screenshots)}] Processing: {screenshot}")
                self.process_screenshot(screenshot)
                
                # Small delay between processing
                if i < len(new_screenshots):
                    time.sleep(2)
            
            logger.info("🎉 All screenshots processed!")
            
        except KeyboardInterrupt:
            logger.info("Watcher stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

def main():
    """Main function"""
    try:
        watcher = LocalScreenshotWatcher()
        watcher.run_watcher()
    except Exception as e:
        logger.error(f"Failed to start watcher: {e}")

if __name__ == "__main__":
    main()
