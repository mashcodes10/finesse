#!/usr/bin/env python3
"""
DSA Coding Problem Screenshot Watcher for GPT-4o
Polls Oracle Cloud Object Storage for new screenshots containing coding/DSA problems,
processes them with OpenAI GPT-4o API in batches of 2, generates Python solutions,
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
from PIL import Image
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/gpt4o_dsa_screenshot_watcher.log'),
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
                'caption': f'🔥 DSA Solution Generated with GPT-4o: `{filename}`'
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
                'Title': '🔥 DSA Problem Solved with GPT-4o',
                'Priority': 'high',
                'Tags': 'coding,dsa,solution,gpt4o'
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

class GPT4oDSAScreenshotWatcher:
    """Main class for watching and processing DSA coding problem screenshots with GPT-4o"""
    
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
        self.screenshot_folder = "gpt4o-screenshots/"  # Dedicated folder for GPT-4o processing
        self.processed_dir = Path("/tmp/gpt4o_dsa_solutions")
        self.processed_dir.mkdir(exist_ok=True)
        
        # Batch processing configuration - Changed to 2 screenshots
        self.batch_size = 2  # Wait for 2 screenshots before processing
        self.pending_screenshots = []  # Queue of screenshots waiting to be processed
        
        # Keep track of processed files
        self.processed_files = set()
        self.state_file = Path("/tmp/gpt4o_dsa_processed_screenshots.json")
        self._load_processed_state()
        
        # Initialize OpenAI
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            sys.exit(1)
        
        # Initialize notification sender
        self.notifier = NotificationSender()
        
        logger.info("GPT-4o DSA Screenshot Watcher initialized successfully - Ready for 2-screenshot batch processing")
        logger.info(f"Configuration: Bucket={self.bucket_name}, Folder={self.screenshot_folder}, Namespace={self.namespace}")
        logger.info(f"State file: {self.state_file}")
        logger.info(f"Solutions directory: {self.processed_dir}")
    
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
            logger.debug(f"Checking for screenshots in bucket: {self.bucket_name}, folder: {self.screenshot_folder}")
            
            # List objects in gpt4o-screenshots/ prefix
            list_objects_response = self.object_storage.list_objects(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                prefix=self.screenshot_folder,
                fields="name,timeCreated"
            )
            
            # Debug: Log all objects found
            total_objects = len(list_objects_response.data.objects) if list_objects_response.data.objects else 0
            logger.info(f"Total objects found in {self.screenshot_folder}: {total_objects}")
            
            new_screenshots = []
            processed_count = 0
            non_png_count = 0
            
            for obj in list_objects_response.data.objects:
                object_name = obj.name
                logger.debug(f"Found object: {object_name}")
                
                # Skip if already processed
                if object_name in self.processed_files:
                    processed_count += 1
                    logger.debug(f"Skipping already processed: {object_name}")
                    continue
                
                # Only process PNG files
                if not object_name.lower().endswith('.png'):
                    non_png_count += 1
                    logger.debug(f"Skipping non-PNG file: {object_name}")
                    continue
                
                new_screenshots.append(object_name)
                logger.debug(f"Added to new screenshots: {object_name}")
            
            logger.info(f"Screenshot analysis: Total={total_objects}, Already processed={processed_count}, Non-PNG={non_png_count}, New={len(new_screenshots)}")
            logger.info(f"Found {len(new_screenshots)} new screenshots: {new_screenshots}")
            return new_screenshots
            
        except Exception as e:
            logger.error(f"Error listing objects: {e}")
            logger.error(f"Bucket: {self.bucket_name}, Folder: {self.screenshot_folder}, Namespace: {self.namespace}")
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
    
    def compress_image_if_needed(self, image_data: bytes, max_size_mb: float = 15.0) -> tuple[bytes, str]:
        """Compress image if it exceeds the size limit while maintaining readability
        
        Note: GPT-4o has a 20MB limit per image, so we target 15MB for safety
        
        Returns: (image_bytes, media_type)
        """
        try:
            # Check current size
            current_size_mb = len(image_data) / (1024 * 1024)
            
            if current_size_mb <= max_size_mb:
                logger.info(f"Image size {current_size_mb:.2f}MB is within limit")
                return image_data, "image/png"
            
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
                    return compressed_data, "image/jpeg"
            
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
                    return compressed_data, "image/jpeg"
                
                scale_factor -= 0.1
            
            # Final fallback - return heavily compressed version
            logger.warning("Using heavily compressed fallback")
            final_img = img.resize((int(original_width * 0.5), int(original_height * 0.5)), Image.Resampling.LANCZOS)
            output_buffer = io.BytesIO()
            final_img.save(output_buffer, format='JPEG', quality=30, optimize=True)
            return output_buffer.getvalue(), "image/jpeg"
            
        except Exception as e:
            logger.error(f"Error compressing image: {e}")
            # Return original if compression fails
            return image_data, "image/png"

    def solve_dsa_problem_batch(self, images_data: List[bytes]) -> Optional[str]:
        """Solve DSA problems from 2 screenshots using OpenAI GPT-4o API with enhanced prompting"""
        try:
            # Compress and encode all images to base64
            base64_images = []
            image_info = []
            for i, image_data in enumerate(images_data):
                # Compress image if needed (GPT-4o has 20MB limit per image)
                compressed_image_data, media_type = self.compress_image_if_needed(image_data, max_size_mb=15.0)
                base64_image = base64.b64encode(compressed_image_data).decode('utf-8')
                base64_images.append(base64_image)
                image_info.append(media_type)
                
                # Log the final sizes
                final_size_mb = len(compressed_image_data) / (1024 * 1024)
                logger.info(f"Image {i+1} compressed size: {final_size_mb:.2f}MB, format: {media_type}")
            
            # Enhanced prompt for DSA problem solving with test case fixing
            content = [
                {
                    "type": "text",
                    "text": f"""You are an expert DSA (Data Structures & Algorithms) problem solver and coding interview specialist. I'm providing you with {len(base64_images)} screenshots that contain coding problems, algorithmic challenges, or failed test cases that need solutions.

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
                }
            ]
            
            # Add all images to the content
            for i, base64_image in enumerate(base64_images):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_info[i]};base64,{base64_image}"
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
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "max_completion_tokens": 4000  # Increased for comprehensive solutions
            }
            
            # Log the request details for debugging
            logger.info(f"Sending DSA problem batch request to GPT-4o with {len(base64_images)} images")
            logger.info(f"Payload model: {payload['model']}")
            logger.info(f"Payload max_completion_tokens: {payload['max_completion_tokens']}")
            
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            
            # Log the full response for debugging
            logger.info(f"GPT-4o API response status: {response.status_code}")
            logger.info(f"GPT-4o API response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Full GPT-4o response structure: {json.dumps(result, indent=2)}")
                
                # Check if choices exist and have content
                if 'choices' not in result or len(result['choices']) == 0:
                    logger.error("No choices in GPT-4o response")
                    return None
                
                if 'message' not in result['choices'][0] or 'content' not in result['choices'][0]['message']:
                    logger.error("No message content in GPT-4o response")
                    return None
                
                extracted_solution = result['choices'][0]['message']['content']
                if extracted_solution is None:
                    extracted_solution = ""
                else:
                    extracted_solution = extracted_solution.strip()
                
                usage = result.get('usage', {})
                
                logger.info(f"GPT-4o DSA batch processing successful. Tokens: {usage.get('total_tokens', 'unknown')}")
                
                # Log the actual response for debugging
                logger.info(f"GPT-4o response length: {len(extracted_solution)} characters")
                if extracted_solution:
                    logger.info(f"GPT-4o response preview: {extracted_solution[:500]}...")
                else:
                    logger.error("GPT-4o returned empty content despite successful API call")
                
                # Process the solution
                if not extracted_solution:
                    logger.error("Empty response from GPT-4o - investigating...")
                    logger.error(f"Full response for debugging: {json.dumps(result, indent=2)}")
                    return None
                
                logger.info("Successfully generated DSA problem solution from screenshot batch with GPT-4o")
                return extracted_solution
            else:
                logger.error(f"GPT-4o API error: {response.status_code}")
                logger.error(f"Response headers: {dict(response.headers)}")
                logger.error(f"Response text: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error solving DSA problem with GPT-4o batch: {e}")
            return None

    def save_dsa_solution(self, solution: str, screenshot_names: List[str]) -> str:
        """Save DSA solution to a .py file"""
        try:
            # Generate filename based on batch processing
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            py_filename = f"gpt4o_dsa_solution_batch_{timestamp}_{len(screenshot_names)}screenshots.py"
            py_filepath = self.processed_dir / py_filename
            
            # Add header comment
            header = f"""# DSA Problem Solution - Generated from {len(screenshot_names)} screenshots with GPT-4o
# Screenshots analyzed: {', '.join([Path(name).name for name in screenshot_names])}
# Processed at: {datetime.now().isoformat()}
# Auto-generated by GPT-4o DSA Screenshot Watcher with OpenAI GPT-4o
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
            print(f"🔥 DSA PROBLEM SOLUTION GENERATED WITH GPT-4o - BATCH PROCESSING ({len(screenshot_names)} screenshots)")
            print(border_char * border_length)
            
            # Screenshot info
            print(f"📸 Screenshots analyzed:")
            for i, name in enumerate(screenshot_names, 1):
                print(f"   {i}. {Path(name).name}")
            
            print(f"💾 Solution saved as: {filename}")
            print(f"⏰ Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🤖 Powered by: GPT-4o")
            
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
            print(f"✅ DSA Solution complete! Full file saved to: /tmp/gpt4o_dsa_solutions/{filename}")
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
        """Process a batch of 2 screenshots together for DSA problem solving"""
        logger.info(f"🔄 Processing DSA batch of {len(screenshot_names)} screenshots with GPT-4o")
        
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
            
            # Solve DSA problem using GPT-4o batch processing
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
            message = f"🔥 **DSA Solution Generated with GPT-4o!**\n\n📸 Analyzed {len(screenshot_names)} screenshots:\n{screenshot_list}\n\n💾 Solution saved as: `{py_filename}`\n⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🤖 Powered by: GPT-4o\n\n🚀 Includes multiple approaches, optimizations, and comprehensive test cases!"
            
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
                prefix=self.screenshot_folder,
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
        
        logger.info(f"Starting GPT-4o DSA Screenshot Watcher (polling every {poll_interval} seconds)")
        logger.info(f"📸 Monitoring folder: {self.screenshot_folder} in bucket: {self.bucket_name}")
        logger.info("📸 Waiting for NEW coding problem screenshots to be uploaded...")
        logger.info(f"🔥 Batch processing: Will process {self.batch_size} screenshots together for comprehensive DSA solutions with GPT-4o")
        
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
                        
                        logger.info(f"🚀 Processing DSA batch of {len(batch_to_process)} screenshots with GPT-4o")
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
                logger.info("GPT-4o DSA Screenshot Watcher stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

def debug_screenshots():
    """Debug function to check what screenshots are available"""
    try:
        watcher = GPT4oDSAScreenshotWatcher()
        print(f"🔍 Debugging screenshot detection...")
        print(f"📁 Bucket: {watcher.bucket_name}")
        print(f"📂 Folder: {watcher.screenshot_folder}")
        print(f"🌐 Namespace: {watcher.namespace}")
        
        # Get all screenshots (including processed ones)
        try:
            list_objects_response = watcher.object_storage.list_objects(
                namespace_name=watcher.namespace,
                bucket_name=watcher.bucket_name,
                prefix=watcher.screenshot_folder,
                fields="name,timeCreated"
            )
            
            if list_objects_response.data.objects:
                print(f"\n📸 Found {len(list_objects_response.data.objects)} total objects:")
                for i, obj in enumerate(list_objects_response.data.objects, 1):
                    status = "✅ NEW" if obj.name not in watcher.processed_files else "⏭️ PROCESSED"
                    file_type = "🖼️ PNG" if obj.name.lower().endswith('.png') else "📄 OTHER"
                    print(f"   {i}. {obj.name} - {file_type} - {status}")
            else:
                print("❌ No objects found in the specified folder!")
                print("💡 Make sure screenshots are being uploaded to the correct folder.")
                
        except Exception as e:
            print(f"❌ Error accessing Oracle Cloud: {e}")
            
        # Check processed state
        print(f"\n📋 Processed files state:")
        print(f"   State file: {watcher.state_file}")
        print(f"   Processed count: {len(watcher.processed_files)}")
        if watcher.processed_files:
            print("   Processed files:")
            for f in list(watcher.processed_files)[:5]:  # Show first 5
                print(f"     - {f}")
            if len(watcher.processed_files) > 5:
                print(f"     ... and {len(watcher.processed_files) - 5} more")
                
    except Exception as e:
        print(f"❌ Debug failed: {e}")

def main():
    """Main function"""
    import sys
    
    # Check for debug flag
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        debug_screenshots()
        return
    
    try:
        watcher = GPT4oDSAScreenshotWatcher()
        watcher.run_dsa_watcher(poll_interval=30)  # Poll every 30 seconds
    except Exception as e:
        logger.error(f"Failed to start GPT-4o DSA screenshot watcher: {e}")
        print("Make sure all environment variables are set and Oracle Cloud is configured.")
        print("Required environment variables:")
        print("- OPENAI_API_KEY: Your OpenAI API key for GPT-4o")
        print("- TELEGRAM_BOT_TOKEN: (optional) Telegram bot token")
        print("- TELEGRAM_CHAT_ID: (optional) Telegram chat ID")
        print("- NTFY_TOPIC: (optional) ntfy.sh topic for notifications")
        print("\nDebug mode:")
        print("- python gpt4o_dsa_screenshot_watcher.py --debug  # Check screenshot detection")

if __name__ == "__main__":
    main()
