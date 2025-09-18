#!/usr/bin/env python3
"""
Question Answer Watcher for Oracle Cloud VM
Polls Oracle Cloud Object Storage for new screenshots, processes them with Claude 4 Sonnet Vision API,
and provides comprehensive answers to any type of question (MCQ, coding, general, etc.)
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
import anthropic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/question_answer_watcher.log'),
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
                'caption': f'📝 Question Answer: `{filename}`'
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
                'Title': '❓ Question Answered',
                'Priority': 'default',
                'Tags': 'question,answer'
            }
            
            response = requests.post(url, data=message.encode('utf-8'), headers=headers)
            
            if response.status_code == 200:
                logger.info("Message sent via ntfy")
                
                # Send file content as separate message if provided
                if filename and file_content:
                    file_headers = {
                        'Title': f'📄 {filename}',
                        'Priority': 'low',
                        'Tags': 'file,answer'
                    }
                    
                    # Truncate if too long for ntfy
                    truncated_content = file_content[:2000]
                    if len(file_content) > 2000:
                        truncated_content += "\n\n... (content truncated, see Telegram for full file)"
                    
                    requests.post(url, data=f"```\n{truncated_content}\n```".encode('utf-8'), headers=file_headers)
                
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

class QuestionAnswerWatcher:
    """Main class for watching and processing question screenshots"""
    
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
        self.processed_dir = Path("/tmp/processed_questions")
        self.processed_dir.mkdir(exist_ok=True)
        
        # Batch processing configuration - 2 screenshots
        self.batch_size = 2  # Wait for 2 screenshots before processing
        self.pending_screenshots = []  # Queue of screenshots waiting to be processed
        
        # Keep track of processed files
        self.processed_files = set()
        self.state_file = Path("/tmp/processed_questions.json")
        self._load_processed_state()
        
        # Initialize Claude
        self.claude_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.claude_api_key:
            logger.error("ANTHROPIC_API_KEY environment variable not set")
            sys.exit(1)
        
        self.claude_client = anthropic.Anthropic(api_key=self.claude_api_key)
        
        # Initialize notification sender
        self.notifier = NotificationSender()
        
        logger.info("Question Answer watcher initialized successfully")
    
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
            
            logger.info(f"Found {len(new_screenshots)} new screenshots for question processing")
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
    
    def answer_question_with_claude(self, images_data: List[bytes]) -> Optional[str]:
        """Answer any type of question using Claude 4 Sonnet Vision API"""
        try:
            # Encode all images to base64
            base64_images = []
            for image_data in images_data:
                base64_image = base64.b64encode(image_data).decode('utf-8')
                base64_images.append(base64_image)
            
            # Prepare content for Claude
            content_parts = [
                {
                    "type": "text",
                    "text": f"You are an expert tutor and problem solver. I'm sending you {len(base64_images)} screenshots that may contain any type of question: Multiple Choice Questions (MCQ), coding problems, math problems, science questions, general knowledge, or any other academic question. Analyze all screenshots together to understand the complete context. Your task is to:\n\n1) **Question Analysis**: Identify what type of question it is and what it's asking for\n2) **Answer Explanation**: Provide a clear, detailed answer with step-by-step explanation\n3) **Additional Context**: If it's an MCQ, explain why other options are wrong. If it's coding, provide the solution with explanation. If it's conceptual, provide comprehensive explanation\n4) **Examples**: Include relevant examples or similar problems if helpful\n5) **Key Takeaways**: Summarize the main concepts or learning points\n\nFormat your response as:\n**Question Type:**\n[Type of question identified]\n\n**Question Analysis:**\n[What the question is asking]\n\n**Answer:**\n[Clear, detailed answer]\n\n**Explanation:**\n[Step-by-step explanation]\n\n**Additional Context:**\n[Why other options are wrong (for MCQ) or additional insights]\n\n**Examples:**\n[Relevant examples if applicable]\n\n**Key Takeaways:**\n[Main concepts and learning points]\n\nIf there's no question visible in any screenshot, return 'NO_QUESTION_FOUND'."
                }
            ]
            
            # Add all images to the content
            for i, base64_image in enumerate(base64_images):
                content_parts.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64_image
                    }
                })
                content_parts.append({
                    "type": "text",
                    "text": f"Question Screenshot {i+1} of {len(base64_images)} ↑"
                })
            
            # Use Claude API
            response = self.claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,  # Increased for comprehensive answers
                messages=[
                    {
                        "role": "user",
                        "content": content_parts
                    }
                ]
            )
            
            extracted_text = response.content[0].text.strip()
            
            logger.info(f"Claude 4 Sonnet question answering successful. Tokens: {response.usage.input_tokens + response.usage.output_tokens}")
            
            if extracted_text == 'NO_QUESTION_FOUND' or not extracted_text:
                logger.info("No question found in screenshot batch")
                return None
            
            return extracted_text
                
        except Exception as e:
            logger.error(f"Error answering question with Claude 4 Sonnet: {e}")
            return None
    
    def save_answer(self, answer: str, original_filename: str) -> str:
        """Save answer to a .txt file"""
        try:
            # Generate filename based on original screenshot name
            base_name = Path(original_filename).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            txt_filename = f"{base_name}_{timestamp}.txt"
            txt_filepath = self.processed_dir / txt_filename
            
            # Add header comment
            header = f"""# Question Answer from screenshot: {original_filename}
# Processed at: {datetime.now().isoformat()}
# Auto-generated by Question Answer Watcher

"""
            
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write(header + answer)
            
            logger.info(f"Saved answer to: {txt_filename}")
            return txt_filename
            
        except Exception as e:
            logger.error(f"Error saving answer: {e}")
            return None

    def _display_answer(self, answer: str, screenshot_names: List[str], filename: str):
        """Display answer in terminal with nice formatting"""
        try:
            # Create a nice terminal display
            border_char = "="
            border_length = 80
            
            # Header
            print("\n" + border_char * border_length)
            print(f"❓ QUESTION ANSWERED ({len(screenshot_names)} screenshots)")
            print(border_char * border_length)
            
            # Screenshot info
            print(f"📸 Question screenshots:")
            for i, name in enumerate(screenshot_names, 1):
                print(f"   {i}. {name}")
            
            print(f"📝 Saved as: {filename}")
            print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Answer section
            print(f"\n{'❓ ANSWER:':^{border_length}}")
            print(border_char * border_length)
            
            # Display answer with line numbers
            answer_lines = answer.split('\n')
            for i, line in enumerate(answer_lines, 1):
                # Add line numbers for better readability
                line_num = f"{i:3d}| "
                print(f"{line_num}{line}")
            
            print(border_char * border_length)
            print(f"✅ Answer processing complete! File saved to: /tmp/processed_questions/{filename}")
            print(border_char * border_length + "\n")
            
            # Also log for file logging
            logger.info("❓ QUESTION ANSWER DISPLAYED IN TERMINAL")
            
        except Exception as e:
            logger.error(f"Error displaying answer: {e}")
            # Fallback: just log the answer
            logger.info("ANSWER:")
            for line in answer.split('\n'):
                logger.info(line)
    
    def process_question_batch(self, screenshot_names: List[str]):
        """Process a batch of 2 question screenshots together with Claude 4 Sonnet"""
        logger.info(f"🔄 Processing batch of {len(screenshot_names)} question screenshots with Claude 4 Sonnet")
        
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
            
            # Answer question using Claude 4 Sonnet
            answer = self.answer_question_with_claude(images_data)
            if not answer:
                logger.info("No question found in screenshot batch")
                # Mark all as processed
                for screenshot_name in screenshot_names:
                    self.processed_files.add(screenshot_name)
                self._save_processed_state()
                return True
            
            # Save answer with batch identifier
            batch_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            txt_filename = f"question_batch_{batch_timestamp}_{len(screenshot_names)}screenshots.txt"
            txt_filepath = self.processed_dir / txt_filename
            
            header = f"""# Question Answer from {len(screenshot_names)} screenshots processed together with Claude 4 Sonnet
# Screenshots: {', '.join(screenshot_names)}
# Processed at: {datetime.now().isoformat()}
# Batch processing - Claude 4 Sonnet analyzed all screenshots for comprehensive answer

"""
            
            with open(txt_filepath, 'w', encoding='utf-8') as f:
                f.write(header + answer)
            
            logger.info(f"💾 Saved batch answer to: {txt_filename}")
            
            # Display the answer in terminal
            self._display_answer(answer, screenshot_names, txt_filename)
            
            # Send notification
            screenshot_list = '\n'.join([f"   • {name}" for name in screenshot_names])
            message = f"❓ **Question Answered!**\n\n📸 Processed {len(screenshot_names)} screenshots:\n{screenshot_list}\n\n📝 Saved as: `{txt_filename}`\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            self.notifier.send_notification(message, txt_filename, answer)
            
            # Mark all screenshots as processed
            for screenshot_name in screenshot_names:
                self.processed_files.add(screenshot_name)
            self._save_processed_state()
            
            logger.info(f"✅ Successfully processed batch of {len(screenshot_names)} question screenshots")
            return True
            
        except Exception as e:
            logger.error(f"Error processing question batch: {e}")
            return False

    def mark_existing_as_processed(self):
        """Mark all existing question screenshots as processed (skip old screenshots)"""
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
            logger.error(f"Error marking existing question screenshots: {e}")

    def run_watcher(self, poll_interval: int = 30, skip_existing: bool = True):
        """Run the main watcher loop"""
        if skip_existing:
            logger.info("🔄 Marking existing screenshots as processed (will only process NEW screenshots)")
            self.mark_existing_as_processed()
        
        logger.info(f"Starting question answer watcher (polling every {poll_interval} seconds)")
        logger.info("❓ Waiting for NEW screenshots to be uploaded for question processing...")
        
        while True:
            try:
                # Get new screenshots
                new_screenshots = self.get_new_screenshots()
                
                if new_screenshots:
                    # Add new screenshots to pending queue
                    self.pending_screenshots.extend(new_screenshots)
                    logger.info(f"❓ Added {len(new_screenshots)} screenshots to queue for question processing. Total pending: {len(self.pending_screenshots)}")
                    
                    # Check if we have enough for batch processing
                    if len(self.pending_screenshots) >= self.batch_size:
                        # Process a batch of 2 screenshots
                        batch_to_process = self.pending_screenshots[:self.batch_size]
                        self.pending_screenshots = self.pending_screenshots[self.batch_size:]
                        
                        logger.info(f"🚀 Processing batch of {len(batch_to_process)} screenshots for question answering with Claude 4 Sonnet")
                        self.process_question_batch(batch_to_process)
                        
                        # Delay between batches
                        time.sleep(5)
                    else:
                        logger.info(f"⏳ Waiting for more screenshots. Need {self.batch_size - len(self.pending_screenshots)} more for question processing")
                
                if not new_screenshots:
                    logger.debug("No new screenshots found for question processing")
                
                # Wait for next poll
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Question answer watcher stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

def main():
    """Main function"""
    try:
        watcher = QuestionAnswerWatcher()
        watcher.run_watcher(poll_interval=30)  # Poll every 30 seconds
    except Exception as e:
        logger.error(f"Failed to start question answer watcher: {e}")
        print("Make sure all environment variables are set and Oracle Cloud is configured.")

if __name__ == "__main__":
    main()
