#!/usr/bin/env python3
"""
Screenshot Watcher for Oracle Cloud VM
Polls Oracle Cloud Object Storage for new screenshots, processes them with OpenAI GPT-5 Thinking API,
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
        
        # Batch processing configuration
        self.batch_size = 2  # Wait for 2 screenshots before processing
        self.pending_screenshots = []  # Queue of screenshots waiting to be processed
        
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
    
    def extract_code_with_openai_batch(self, images_data: List[bytes]) -> Optional[str]:
        """Extract Python code from multiple screenshots using OpenAI GPT-5 Thinking API"""
        try:
            # Encode all images to base64
            base64_images = []
            for image_data in images_data:
                base64_image = base64.b64encode(image_data).decode('utf-8')
                base64_images.append(base64_image)
            
            # Prepare content with multiple images for OpenAI
            content = [
                {
                    "type": "text",
                    "text": f"You are a Data Structures and Algorithms interview assistant. I'm sending you {len(base64_images)} screenshots that may contain coding problems, algorithm questions, or data structure challenges. Analyze all screenshots together to understand the complete context. Your task is to:\n\n1) **Problem Statement**: Clearly explain what the problem is asking for, including input/output format and constraints\n2) **Clarifying Questions**: Ask 2-3 clarifying questions about the problem (assumptions, constraints, edge cases)\n3) **Solution Approach**: Explain the overall strategy and approach to solve the problem\n4) **Brute Force Solution**: If applicable, provide a brute force approach with detailed explanation and time/space complexity\n5) **Optimal Algorithm**: Provide the most efficient algorithm with step-by-step explanation, data structures used, and complexity analysis\n6) **Python Implementation**: Implement the optimal solution in clean, well-commented Python code\n7) **Test Cases**: Include comprehensive test cases to verify the solution\n\nFormat your response as:\n**Problem Statement:**\n[Clear explanation of what the problem asks]\n\n**Clarifying Questions:**\n- Question 1\n- Question 2\n- Question 3\n\n**Solution Approach:**\n[Overall strategy and approach]\n\n**Brute Force Approach:**\n[Detailed explanation with complexity]\n\n**Optimal Algorithm:**\n[Step-by-step algorithm explanation with data structures and complexity]\n\n**Python Implementation:**\n```python\n[Clean, commented code]\n```\n\n**Test Cases:**\n[Comprehensive test cases with inputs and expected outputs]\n\nIf there's no coding problem visible in any screenshot, return 'NO_PROBLEM_FOUND'."
                }
            ]
            
            # Add all images to the content
            for i, base64_image in enumerate(base64_images):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                })
                content.append({
                    "type": "text",
                    "text": f"Screenshot {i+1} of {len(base64_images)} ↑"
                })
            
            # Prepare the request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai.api_key}"
            }
            
            payload = {
                "model": "gpt-5",
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "max_completion_tokens": 3000
            }
            
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                extracted_text = result['choices'][0]['message']['content'].strip()
                usage = result.get('usage', {})
                
                logger.info(f"GPT-5 Thinking batch processing successful. Tokens: {usage.get('total_tokens', 'unknown')}")
                
                if extracted_text == 'NO_PROBLEM_FOUND' or not extracted_text:
                    logger.info("No coding problem found in screenshot batch")
                    return None
                
                return extracted_text
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting code with GPT-5 Thinking batch: {e}")
            return None

    def extract_code_with_openai(self, image_data: bytes) -> Optional[str]:
        """Extract Python code from screenshot using OpenAI GPT-5 Thinking API"""
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare content for OpenAI
            content = [
                {
                    "type": "text",
                    "text": "You are a Data Structures and Algorithms interview assistant. Your task is to analyze screenshots that may contain coding problems, algorithm questions, or data structure challenges. Your task is to:\n\n1) **Problem Statement**: Clearly explain what the problem is asking for, including input/output format and constraints\n2) **Clarifying Questions**: Ask 2-3 clarifying questions about the problem (assumptions, constraints, edge cases)\n3) **Solution Approach**: Explain the overall strategy and approach to solve the problem\n4) **Brute Force Solution**: If applicable, provide a brute force approach with detailed explanation and time/space complexity\n5) **Optimal Algorithm**: Provide the most efficient algorithm with step-by-step explanation, data structures used, and complexity analysis\n6) **Python Implementation**: Implement the optimal solution in clean, well-commented Python code\n7) **Test Cases**: Include comprehensive test cases to verify the solution\n\nFormat your response as:\n**Problem Statement:**\n[Clear explanation of what the problem asks]\n\n**Clarifying Questions:**\n- Question 1\n- Question 2\n- Question 3\n\n**Solution Approach:**\n[Overall strategy and approach]\n\n**Brute Force Approach:**\n[Detailed explanation with complexity]\n\n**Optimal Algorithm:**\n[Step-by-step algorithm explanation with data structures and complexity]\n\n**Python Implementation:**\n```python\n[Clean, commented code]\n```\n\n**Test Cases:**\n[Comprehensive test cases with inputs and expected outputs]\n\nIf there's no coding problem visible in the screenshot, return 'NO_PROBLEM_FOUND'."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                }
            ]
            
            # Prepare the request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai.api_key}"
            }
            
            payload = {
                "model": "gpt-5",
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "max_completion_tokens": 2000
            }
            
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                extracted_text = result['choices'][0]['message']['content'].strip()
                
                if extracted_text == 'NO_PROBLEM_FOUND' or not extracted_text:
                    logger.info("No coding problem found in screenshot")
                    return None
                
                logger.info("Successfully extracted code from screenshot with GPT-5 Thinking")
                return extracted_text
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting code with GPT-5 Thinking: {e}")
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
            header = f"""# DSA Interview Analysis from screenshot: {original_filename}
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

    def _display_extracted_code(self, code: str, screenshot_names: List[str], filename: str, is_batch: bool = False):
        """Display extracted Python code in terminal with nice formatting"""
        try:
            # Create a nice terminal display
            border_char = "="
            border_length = 80
            
            # Header
            print("\n" + border_char * border_length)
            if is_batch:
                print(f"🚀 DSA INTERVIEW ANALYSIS - BATCH PROCESSING ({len(screenshot_names)} screenshots)")
            else:
                print(f"🎯 DSA INTERVIEW ANALYSIS")
            print(border_char * border_length)
            
            # Screenshot info
            if is_batch:
                print(f"📸 Screenshots processed:")
                for i, name in enumerate(screenshot_names, 1):
                    print(f"   {i}. {name}")
            else:
                print(f"📸 From: {screenshot_names[0]}")
            
            print(f"📝 Saved as: {filename}")
            print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Code section
            print(f"\n{'🎯 DSA INTERVIEW SOLUTION:':^{border_length}}")
            print(border_char * border_length)
            
            # Display code with line numbers
            code_lines = code.split('\n')
            for i, line in enumerate(code_lines, 1):
                # Add line numbers for better readability
                line_num = f"{i:3d}| "
                print(f"{line_num}{line}")
            
            print(border_char * border_length)
            print(f"✅ DSA Interview analysis complete! File saved to: /tmp/processed_screenshots/{filename}")
            print(border_char * border_length + "\n")
            
            # Also log for file logging
            logger.info("🎯 DSA INTERVIEW ANALYSIS DISPLAYED IN TERMINAL")
            
        except Exception as e:
            logger.error(f"Error displaying extracted code: {e}")
            # Fallback: just log the code
            logger.info("EXTRACTED CODE:")
            for line in code.split('\n'):
                logger.info(line)
    
    def process_screenshot_batch(self, screenshot_names: List[str]):
        """Process a batch of 2 screenshots together with OpenAI GPT-5 Thinking"""
        logger.info(f"🔄 Processing batch of {len(screenshot_names)} screenshots with OpenAI GPT-5 Thinking")
        
        try:
            # Download all screenshots
            images_data = []
            for screenshot_name in screenshot_names:
                image_data = self.download_screenshot(screenshot_name)
                if image_data:
                    images_data.append(image_data)
                else:
                    logger.warning(f"Failed to download {screenshot_name}")
            
            if not images_data:
                logger.error("No screenshots could be downloaded")
                return False
            
            logger.info(f"📥 Downloaded {len(images_data)} screenshots for batch processing")
            
            # Extract code using GPT-5 Thinking batch processing
            extracted_code = self.extract_code_with_openai_batch(images_data)
            if not extracted_code:
                logger.info("No code found in screenshot batch")
                # Mark all as processed
                for screenshot_name in screenshot_names:
                    self.processed_files.add(screenshot_name)
                self._save_processed_state()
                return True
            
            # Save extracted code with batch identifier
            batch_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            py_filename = f"batch_{batch_timestamp}_{len(screenshot_names)}screenshots.py"
            py_filepath = self.processed_dir / py_filename
            
            header = f"""# DSA Interview Analysis from {len(screenshot_names)} screenshots processed together with OpenAI GPT-5 Thinking
# Screenshots: {', '.join(screenshot_names)}
# Processed at: {datetime.now().isoformat()}
# Batch processing - OpenAI GPT-5 Thinking analyzed all screenshots for comprehensive DSA interview solution

"""
            
            with open(py_filepath, 'w', encoding='utf-8') as f:
                f.write(header + extracted_code)
            
            logger.info(f"💾 Saved batch extracted code to: {py_filename}")
            
            # Display the extracted code in terminal
            self._display_extracted_code(extracted_code, screenshot_names, py_filename, is_batch=True)
            
            # Send notification
            screenshot_list = '\n'.join([f"   • {name}" for name in screenshot_names])
            message = f"🎯 **GPT-5 Thinking DSA Analysis Complete!**\n\n📸 Processed {len(screenshot_names)} screenshots:\n{screenshot_list}\n\n📝 Saved as: `{py_filename}`\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            self.notifier.send_notification(message, py_filename, extracted_code)
            
            # Mark all screenshots as processed
            for screenshot_name in screenshot_names:
                self.processed_files.add(screenshot_name)
            self._save_processed_state()
            
            logger.info(f"✅ Successfully processed batch of {len(screenshot_names)} screenshots")
            return True
            
        except Exception as e:
            logger.error(f"Error processing screenshot batch: {e}")
            return False

    def process_screenshot(self, object_name: str):
        """Process a single screenshot (fallback method)"""
        logger.info(f"Processing single screenshot: {object_name}")
        
        try:
            # Download screenshot
            image_data = self.download_screenshot(object_name)
            if not image_data:
                return False
            
            # Extract code using GPT-5 Thinking
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
            
            # Display the extracted code in terminal
            self._display_extracted_code(extracted_code, [object_name], py_filename, is_batch=False)
            
            # Send notification
            message = f"🎯 **DSA Interview Analysis Complete!**\n\n📸 From: `{object_name}`\n📝 Saved as: `{py_filename}`\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
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
                
                if new_screenshots:
                    # Add new screenshots to pending queue
                    self.pending_screenshots.extend(new_screenshots)
                    logger.info(f"📸 Added {len(new_screenshots)} screenshots to queue. Total pending: {len(self.pending_screenshots)}")
                    
                    # Check if we have enough for batch processing
                    if len(self.pending_screenshots) >= self.batch_size:
                        # Process a batch of 2 screenshots
                        batch_to_process = self.pending_screenshots[:self.batch_size]
                        self.pending_screenshots = self.pending_screenshots[self.batch_size:]
                        
                        logger.info(f"🚀 Processing batch of {len(batch_to_process)} screenshots with GPT-5 Thinking")
                        self.process_screenshot_batch(batch_to_process)
                        
                        # Delay between batches
                        time.sleep(5)
                    else:
                        logger.info(f"⏳ Waiting for more screenshots. Need {self.batch_size - len(self.pending_screenshots)} more for batch processing")
                
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
