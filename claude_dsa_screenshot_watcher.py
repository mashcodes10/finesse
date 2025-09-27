#!/usr/bin/env python3
"""
DSA Coding Problem Screenshot Watcher for Claude 4 Sonnet
Polls Oracle Cloud Object Storage for new screenshots containing coding/DSA problems,
processes them with Anthropic Claude 4 Sonnet API in batches of 3, generates Python solutions,
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
import anthropic
from PIL import Image
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/claude_dsa_screenshot_watcher.log'),
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
                'caption': f'🔥 DSA Solution Generated with Claude 4 Sonnet: `{filename}`'
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
                'Title': '🔥 DSA Problem Solved with Claude',
                'Priority': 'high',
                'Tags': 'coding,dsa,solution,claude'
            }
            
            response = requests.post(url, data=message.encode('utf-8'), headers=headers)
            
            if response.status_code == 200:
                logger.info("Message sent via ntfy")
                
                # Send file content as separate message if provided
                if filename and file_content:
                    file_headers = {
                        'Title': f'📄 {filename}',
                        'Priority': 'low',
                        'Tags': 'file,python,solution'
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

class ClaudeDSAScreenshotWatcher:
    """Main class for watching and processing DSA coding problem screenshots with Claude 4 Sonnet"""
    
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
        self.processed_dir = Path("/tmp/claude_dsa_solutions")
        self.processed_dir.mkdir(exist_ok=True)
        
        # Batch processing configuration - Changed to 3 screenshots
        self.batch_size = 3  # Wait for 3 screenshots before processing
        self.pending_screenshots = []  # Queue of screenshots waiting to be processed
        
        # Keep track of processed files
        self.processed_files = set()
        self.state_file = Path("/tmp/claude_dsa_processed_screenshots.json")
        self._load_processed_state()
        
        # Initialize Claude
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not anthropic_api_key:
            logger.error("ANTHROPIC_API_KEY environment variable not set")
            sys.exit(1)
        
        self.claude_client = anthropic.Anthropic(api_key=anthropic_api_key)
        
        # Initialize notification sender
        self.notifier = NotificationSender()
        
        logger.info("Claude DSA Screenshot Watcher initialized successfully - Ready for 3-screenshot batch processing")
    
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
    
    def compress_image_if_needed(self, image_data: bytes, max_size_mb: float = 4.5) -> bytes:
        """Compress image if it exceeds the size limit while maintaining readability"""
        try:
            # Check current size
            current_size_mb = len(image_data) / (1024 * 1024)
            
            if current_size_mb <= max_size_mb:
                logger.info(f"Image size {current_size_mb:.2f}MB is within limit")
                return image_data
            
            logger.info(f"Image size {current_size_mb:.2f}MB exceeds limit, compressing...")
            
            # Open image with PIL
            img = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary (for JPEG compression)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Calculate compression ratio needed
            target_size_bytes = int(max_size_mb * 1024 * 1024)
            compression_ratio = target_size_bytes / len(image_data)
            
            # Start with quality based on compression ratio needed
            if compression_ratio > 0.7:
                quality = 85
            elif compression_ratio > 0.5:
                quality = 75
            elif compression_ratio > 0.3:
                quality = 65
            else:
                quality = 55
            
            # Try different compression levels
            for attempt_quality in [quality, quality-10, quality-20, 50, 40, 30]:
                if attempt_quality < 20:
                    attempt_quality = 20
                
                # Compress image
                output_buffer = io.BytesIO()
                img.save(output_buffer, format='JPEG', quality=attempt_quality, optimize=True)
                compressed_data = output_buffer.getvalue()
                compressed_size_mb = len(compressed_data) / (1024 * 1024)
                
                logger.info(f"Compression attempt: quality={attempt_quality}, size={compressed_size_mb:.2f}MB")
                
                if compressed_size_mb <= max_size_mb:
                    logger.info(f"Successfully compressed from {current_size_mb:.2f}MB to {compressed_size_mb:.2f}MB")
                    return compressed_data
            
            # If still too large, try resizing
            logger.warning("Compression alone not sufficient, trying resize...")
            
            # Reduce image dimensions while maintaining aspect ratio
            original_width, original_height = img.size
            scale_factor = 0.8  # Start with 80% scale
            
            while scale_factor > 0.3:  # Don't go below 30% to maintain readability
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
                
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                output_buffer = io.BytesIO()
                resized_img.save(output_buffer, format='JPEG', quality=75, optimize=True)
                compressed_data = output_buffer.getvalue()
                compressed_size_mb = len(compressed_data) / (1024 * 1024)
                
                logger.info(f"Resize attempt: scale={scale_factor:.1f}, size={compressed_size_mb:.2f}MB")
                
                if compressed_size_mb <= max_size_mb:
                    logger.info(f"Successfully resized and compressed from {current_size_mb:.2f}MB to {compressed_size_mb:.2f}MB")
                    return compressed_data
                
                scale_factor -= 0.1
            
            # Final fallback - return heavily compressed version
            logger.warning("Using heavily compressed fallback")
            final_img = img.resize((int(original_width * 0.5), int(original_height * 0.5)), Image.Resampling.LANCZOS)
            output_buffer = io.BytesIO()
            final_img.save(output_buffer, format='JPEG', quality=30, optimize=True)
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error compressing image: {e}")
            # Return original if compression fails
            return image_data

    def solve_dsa_problem_batch(self, images_data: List[bytes]) -> Optional[str]:
        """Solve DSA problems from 3 screenshots using Claude 4 Sonnet API with enhanced prompting"""
        try:
            # Compress and encode all images to base64
            base64_images = []
            for i, image_data in enumerate(images_data):
                # Compress image if needed (Claude has 5MB limit)
                compressed_image_data = self.compress_image_if_needed(image_data, max_size_mb=4.5)
                base64_image = base64.b64encode(compressed_image_data).decode('utf-8')
                base64_images.append(base64_image)
                
                # Log the final size
                final_size_mb = len(compressed_image_data) / (1024 * 1024)
                logger.info(f"Image {i+1} final size: {final_size_mb:.2f}MB")
            
            # Enhanced prompt for DSA problem solving with test case fixing
            prompt_text = f"""You are an expert DSA (Data Structures & Algorithms) problem solver and coding interview specialist. I'm providing you with {len(base64_images)} screenshots that contain coding problems, algorithmic challenges, or failed test cases that need solutions.

TASK OVERVIEW:
Please read the problems from the screenshots and provide comprehensive Python solutions. Analyze all {len(base64_images)} screenshots together to understand the complete problem context.

SPECIFIC REQUIREMENTS:

1. **PROBLEM EXTRACTION & ANALYSIS:**
   - Read and extract the complete problem statement from the screenshots
   - Identify input/output format, constraints, and examples
   - Determine the problem category (arrays, strings, trees, graphs, DP, etc.)
   - Note any failed test cases or error messages shown in the screenshots

2. **SOLUTION STRATEGY:**
   - Provide multiple approaches (brute force → optimal) when applicable
   - For each approach: explain algorithm, time/space complexity
   - If screenshots show failed test cases, identify the issues and provide correct solutions
   - Handle edge cases and constraints properly

3. **CODE REQUIREMENTS:**
   - Generate clean, well-commented Python code
   - Include proper function signatures with type hints
   - Add comprehensive test cases covering edge cases
   - If fixing failed test cases, explain what was wrong and how it's fixed
   - Ensure code is executable and handles all requirements

4. **OUTPUT FORMAT:**
   Please structure your response as follows:

   ## Problem Analysis
   [Brief description of the problem extracted from screenshots]

   ## Approach 1: [Name] - O(time) time, O(space) space
   [Algorithm explanation]
   
   ```python
   [Clean Python implementation]
   ```

   ## Approach 2: [Name] - O(time) time, O(space) space  
   [Algorithm explanation]
   
   ```python
   [Optimized Python implementation]
   ```

   ## Test Cases & Validation
   ```python
   [Comprehensive test cases including edge cases]
   ```

   ## Failed Test Case Analysis (if applicable)
   [If screenshots show failed tests, explain the issues and how your solution fixes them]

CRITICAL NOTES:
- Always assume there are coding problems in the screenshots
- Provide working, executable Python code
- Focus on correctness first, then optimization
- If problem details are unclear, make reasonable assumptions and state them
- Include comments explaining complex logic
- Ensure code handles all edge cases mentioned in constraints
- If there are failed test cases in the screenshots, provide solutions that fix those specific failures"""

            # Prepare messages for Claude
            content = [
                {
                    "type": "text",
                    "text": prompt_text
                }
            ]
            
            # Add all images to the content
            for i, base64_image in enumerate(base64_images):
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64_image
                    }
                })
            
            # Log the request details for debugging
            logger.info(f"Sending DSA problem batch request to Claude 4 Sonnet with {len(base64_images)} images")
            
            # Make the API call to Claude
            message = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20250514",
                max_tokens=4000,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            )
            
            # Extract the response
            if message.content and len(message.content) > 0:
                extracted_solution = message.content[0].text.strip()
                
                logger.info(f"Claude 4 Sonnet DSA batch processing successful. Tokens: {message.usage.input_tokens + message.usage.output_tokens}")
                
                # Log the actual response for debugging
                logger.info(f"Claude response length: {len(extracted_solution)} characters")
                if extracted_solution:
                    logger.info(f"Claude response preview: {extracted_solution[:500]}...")
                else:
                    logger.error("Claude returned empty content despite successful API call")
                
                # Process the solution
                if not extracted_solution:
                    logger.error("Empty response from Claude - investigating...")
                    return None
                
                logger.info("Successfully generated DSA problem solution from screenshot batch with Claude")
                return extracted_solution
            else:
                logger.error("No content in Claude response")
                return None
                
        except Exception as e:
            logger.error(f"Error solving DSA problem with Claude 4 Sonnet batch: {e}")
            return None

    def save_dsa_solution(self, solution: str, screenshot_names: List[str]) -> str:
        """Save DSA solution to a .py file"""
        try:
            # Generate filename based on batch processing
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            py_filename = f"claude_dsa_solution_batch_{timestamp}_{len(screenshot_names)}screenshots.py"
            py_filepath = self.processed_dir / py_filename
            
            # Add header comment
            header = f"""# DSA Problem Solution - Generated from {len(screenshot_names)} screenshots with Claude 4 Sonnet
# Screenshots analyzed: {', '.join([Path(name).name for name in screenshot_names])}
# Processed at: {datetime.now().isoformat()}
# Auto-generated by Claude DSA Screenshot Watcher with Anthropic Claude 4 Sonnet
# 
# This solution handles:
# - Complete problem analysis from multiple screenshots
# - Optimized algorithmic approaches 
# - Comprehensive test cases
# - Failed test case corrections (if applicable)

'''
USAGE:
Run this file directly to test the solutions:
python {py_filename}

The solution includes multiple approaches and comprehensive test cases.
'''

"""
            
            with open(py_filepath, 'w', encoding='utf-8') as f:
                f.write(header + solution)
            
            logger.info(f"Saved DSA solution to: {py_filename}")
            return py_filename
            
        except Exception as e:
            logger.error(f"Error saving DSA solution: {e}")
            return None

    def _display_dsa_solution(self, solution: str, screenshot_names: List[str], filename: str):
        """Display complete DSA solution in terminal with enhanced formatting"""
        try:
            # Create a nice terminal display
            border_char = "="
            border_length = 100
            
            # Header
            print("\n" + border_char * border_length)
            print(f"🔥 DSA PROBLEM SOLUTION GENERATED WITH CLAUDE 4 SONNET - BATCH PROCESSING ({len(screenshot_names)} screenshots)")
            print(border_char * border_length)
            
            # Screenshot info
            print(f"📸 Screenshots analyzed:")
            for i, name in enumerate(screenshot_names, 1):
                print(f"   {i}. {Path(name).name}")
            
            print(f"💾 Solution saved as: {filename}")
            print(f"⏰ Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🤖 Powered by: Claude 4 Sonnet")
            
            # Solution section
            print(f"\n{'🚀 COMPLETE DSA SOLUTION:':^{border_length}}")
            print(border_char * border_length)
            
            # Display FULL solution with line numbers
            solution_lines = solution.split('\n')
            
            for i, line in enumerate(solution_lines, 1):
                # Add line numbers for better readability
                line_num = f"{i:3d}| "
                print(f"{line_num}{line}")
            
            print(border_char * border_length)
            print(f"✅ DSA Solution complete! Full file saved to: /tmp/claude_dsa_solutions/{filename}")
            print(f"📊 Total lines generated: {len(solution_lines)}")
            print(border_char * border_length + "\n")
            
            # Also log for file logging
            logger.info("🔥 COMPLETE DSA SOLUTION DISPLAYED IN TERMINAL")
            
        except Exception as e:
            logger.error(f"Error displaying DSA solution: {e}")
            # Fallback: just log the solution
            logger.info("DSA SOLUTION:")
            for line in solution.split('\n'):
                logger.info(line)
    
    def process_dsa_screenshot_batch(self, screenshot_names: List[str]):
        """Process a batch of 3 screenshots together for DSA problem solving"""
        logger.info(f"🔄 Processing DSA batch of {len(screenshot_names)} screenshots with Claude 4 Sonnet")
        
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
            
            logger.info(f"📥 Downloaded {len(images_data)} screenshots for DSA batch processing")
            
            # Solve DSA problem using Claude 4 Sonnet batch processing
            dsa_solution = self.solve_dsa_problem_batch(images_data)
            if not dsa_solution:
                logger.info("No DSA solution generated from screenshot batch")
                # Mark all as processed
                for screenshot_name in screenshot_names:
                    self.processed_files.add(screenshot_name)
                self._save_processed_state()
                return True
            
            # Save DSA solution
            py_filename = self.save_dsa_solution(dsa_solution, screenshot_names)
            if not py_filename:
                return False
            
            # Display the solution in terminal
            self._display_dsa_solution(dsa_solution, screenshot_names, py_filename)
            
            # Send notification
            screenshot_list = '\n'.join([f"   • {Path(name).name}" for name in screenshot_names])
            message = f"🔥 **DSA Solution Generated with Claude 4 Sonnet!**\n\n📸 Analyzed {len(screenshot_names)} screenshots:\n{screenshot_list}\n\n💾 Solution saved as: `{py_filename}`\n⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🤖 Powered by: Claude 4 Sonnet\n\n🚀 Includes multiple approaches, optimizations, and comprehensive test cases!"
            
            self.notifier.send_notification(message, py_filename, dsa_solution)
            
            # Mark all screenshots as processed
            for screenshot_name in screenshot_names:
                self.processed_files.add(screenshot_name)
            self._save_processed_state()
            
            logger.info(f"✅ Successfully processed DSA batch of {len(screenshot_names)} screenshots")
            return True
            
        except Exception as e:
            logger.error(f"Error processing DSA screenshot batch: {e}")
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

    def run_dsa_watcher(self, poll_interval: int = 30, skip_existing: bool = True):
        """Run the main DSA watcher loop"""
        if skip_existing:
            logger.info("🔄 Marking existing screenshots as processed (will only process NEW screenshots)")
            self.mark_existing_as_processed()
        
        logger.info(f"Starting Claude DSA Screenshot Watcher (polling every {poll_interval} seconds)")
        logger.info("📸 Waiting for NEW coding problem screenshots to be uploaded...")
        logger.info(f"🔥 Batch processing: Will process {self.batch_size} screenshots together for comprehensive DSA solutions with Claude 4 Sonnet")
        
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
                        # Process a batch of 3 screenshots
                        batch_to_process = self.pending_screenshots[:self.batch_size]
                        self.pending_screenshots = self.pending_screenshots[self.batch_size:]
                        
                        logger.info(f"🚀 Processing DSA batch of {len(batch_to_process)} screenshots with Claude 4 Sonnet")
                        self.process_dsa_screenshot_batch(batch_to_process)
                        
                        # Delay between batches
                        time.sleep(10)  # Slightly longer delay for comprehensive processing
                    else:
                        logger.info(f"⏳ Waiting for more screenshots. Need {self.batch_size - len(self.pending_screenshots)} more for DSA batch processing")
                
                if not new_screenshots:
                    logger.debug("No new screenshots found")
                
                # Wait for next poll
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Claude DSA Screenshot Watcher stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

def main():
    """Main function"""
    try:
        watcher = ClaudeDSAScreenshotWatcher()
        watcher.run_dsa_watcher(poll_interval=30)  # Poll every 30 seconds
    except Exception as e:
        logger.error(f"Failed to start Claude DSA screenshot watcher: {e}")
        print("Make sure all environment variables are set and Oracle Cloud is configured.")
        print("Required environment variables:")
        print("- ANTHROPIC_API_KEY: Your Anthropic API key for Claude 4 Sonnet")
        print("- TELEGRAM_BOT_TOKEN: (optional) Telegram bot token")
        print("- TELEGRAM_CHAT_ID: (optional) Telegram chat ID")
        print("- NTFY_TOPIC: (optional) ntfy.sh topic for notifications")

if __name__ == "__main__":
    main()
