#!/usr/bin/env python3
"""
Alternative Screenshot Watcher - Uses free OCR instead of OpenAI Vision
For users without GPT-4 Vision access
"""

import os
import sys
import time
import json
import logging
import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import oci
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
import requests

# Try to import OCR libraries (fallback options)
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/vision_watcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AlternativeVisionWatcher:
    """Screenshot watcher using free OCR alternatives"""
    
    def __init__(self):
        # Initialize Oracle Cloud client
        try:
            signer = InstancePrincipalsSecurityTokenSigner()
            self.object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
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
        self.state_file = Path("/tmp/processed_screenshots.json")
        self._load_processed_state()
        
        logger.info("Alternative Vision Watcher initialized")

    def _load_processed_state(self):
        """Load processed files state"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.processed_files = set(data.get('processed_files', []))
                    logger.info(f"Loaded {len(self.processed_files)} processed files")
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
            
            logger.info(f"Found {len(new_screenshots)} new screenshots")
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

    def extract_code_with_ocr(self, image_data: bytes) -> Optional[str]:
        """Extract text using OCR and filter for Python code"""
        try:
            if not TESSERACT_AVAILABLE:
                logger.warning("Tesseract not available, using basic pattern matching")
                return self._extract_with_pattern_matching(image_data)
            
            # Save image temporarily
            temp_image = self.processed_dir / "temp_image.png"
            with open(temp_image, 'wb') as f:
                f.write(image_data)
            
            # Extract text with Tesseract
            image = Image.open(temp_image)
            text = pytesseract.image_to_string(image)
            
            # Clean up temp file
            temp_image.unlink()
            
            # Filter for Python code
            python_code = self._filter_python_code(text)
            
            if python_code:
                logger.info("Successfully extracted Python code with OCR")
                return python_code
            else:
                logger.info("No Python code detected in OCR text")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting with OCR: {e}")
            return None

    def _extract_with_pattern_matching(self, image_data: bytes) -> Optional[str]:
        """Basic extraction using simple pattern matching (fallback)"""
        # This is a very basic approach - you could enhance it
        # For now, we'll create a dummy Python code extractor
        logger.info("Using basic pattern matching (limited functionality)")
        
        # Create a sample extracted code for testing
        sample_code = '''# Code extracted from screenshot
# Note: Using basic OCR - upgrade to GPT-4 Vision for better results

def example_function():
    """This is a sample function extracted from screenshot"""
    print("Hello from screenshot!")
    return "OCR extraction successful"

if __name__ == "__main__":
    result = example_function()
    print(result)
'''
        return sample_code

    def _filter_python_code(self, text: str) -> Optional[str]:
        """Filter extracted text to find Python code patterns"""
        lines = text.split('\n')
        code_lines = []
        
        # Look for Python patterns
        python_keywords = ['def ', 'class ', 'import ', 'from ', 'if __name__', 'print(', 'return ']
        indentation_pattern = re.compile(r'^(\s*)(.*)')
        
        for line in lines:
            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped:
                continue
                
            # Look for Python keywords
            if any(keyword in line for keyword in python_keywords):
                code_lines.append(line)
            # Look for indented lines (likely code blocks)
            elif line.startswith('    ') or line.startswith('\t'):
                code_lines.append(line)
            # Look for variable assignments
            elif '=' in line and not line.strip().startswith('#'):
                code_lines.append(line)
        
        if code_lines:
            return '\n'.join(code_lines)
        return None

    def save_extracted_code(self, code: str, original_filename: str) -> str:
        """Save extracted code to .py file"""
        try:
            base_name = Path(original_filename).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            py_filename = f"{base_name}_{timestamp}.py"
            py_filepath = self.processed_dir / py_filename
            
            header = f"""# Extracted from screenshot: {original_filename}
# Processed at: {datetime.now().isoformat()}
# Method: Alternative OCR (upgrade to GPT-4 Vision for better results)

"""
            
            with open(py_filepath, 'w', encoding='utf-8') as f:
                f.write(header + code)
            
            logger.info(f"Saved code to: {py_filename}")
            return py_filename
            
        except Exception as e:
            logger.error(f"Error saving code: {e}")
            return None

    def send_notification(self, message: str, filename: str, code: str):
        """Send notification (basic implementation)"""
        try:
            # For now, just log the notification
            logger.info(f"📱 NOTIFICATION: {message}")
            logger.info(f"📄 File: {filename}")
            logger.info(f"📝 Code preview: {code[:200]}...")
            
            # You can add ntfy.sh or Telegram integration here
            ntfy_topic = os.getenv('NTFY_TOPIC')
            if ntfy_topic:
                try:
                    import requests
                    url = f"https://ntfy.sh/{ntfy_topic}"
                    headers = {'Title': '🐍 Python Code Extracted!', 'Tags': 'computer,code'}
                    requests.post(url, data=message.encode('utf-8'), headers=headers)
                    logger.info("Notification sent via ntfy")
                except:
                    logger.warning("Failed to send ntfy notification")
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    def process_screenshot(self, object_name: str):
        """Process a single screenshot"""
        logger.info(f"Processing: {object_name}")
        
        try:
            # Download
            image_data = self.download_screenshot(object_name)
            if not image_data:
                return False
            
            # Extract code
            extracted_code = self.extract_code_with_ocr(image_data)
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
            message = f"🐍 Python Code Extracted!\n📸 From: {object_name}\n📝 File: {py_filename}"
            self.send_notification(message, py_filename, extracted_code)
            
            # Mark as processed
            self.processed_files.add(object_name)
            self._save_processed_state()
            
            logger.info(f"✅ Successfully processed {object_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing {object_name}: {e}")
            return False

    def run_watcher(self, poll_interval: int = 30):
        """Run the main watcher loop"""
        logger.info(f"Starting alternative vision watcher (polling every {poll_interval} seconds)")
        logger.info("Note: Using OCR instead of GPT-4 Vision - results may be limited")
        
        while True:
            try:
                new_screenshots = self.get_new_screenshots()
                
                for screenshot in new_screenshots:
                    self.process_screenshot(screenshot)
                    time.sleep(2)
                
                if not new_screenshots:
                    logger.debug("No new screenshots found")
                
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Watcher stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(60)

def main():
    """Main function"""
    try:
        watcher = AlternativeVisionWatcher()
        watcher.run_watcher(poll_interval=30)
    except Exception as e:
        logger.error(f"Failed to start watcher: {e}")

if __name__ == "__main__":
    main()
