#!/usr/bin/env python3
"""
Test Full Pipeline: Screenshot → OpenAI → Output
Demonstrates the complete workflow
"""

import subprocess
import time
import oci
import base64
import requests
import os
from pathlib import Path
from datetime import datetime

def test_full_pipeline():
    """Test the complete pipeline end-to-end"""
    
    print("🔬 TESTING COMPLETE PIPELINE")
    print("=" * 50)
    
    # Get API key
    api_key = input("Enter your OpenAI API key: ").strip()
    if not api_key:
        print("❌ No API key provided")
        return
    
    # Step 1: Take a fresh screenshot
    print("\n📸 STEP 1: Taking a fresh screenshot...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = Path(f"/tmp/pipeline_test_{timestamp}.png")
    
    try:
        result = subprocess.run([
            "screencapture", 
            "-x",  # Silent mode
            "-t", "png",
            str(screenshot_path)
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            file_size = screenshot_path.stat().st_size / (1024 * 1024)
            print(f"✅ Screenshot captured: {screenshot_path.name}")
            print(f"📏 Size: {file_size:.2f} MB")
        else:
            print(f"❌ Screenshot failed: {result.stderr}")
            return
            
    except Exception as e:
        print(f"❌ Error taking screenshot: {e}")
        return
    
    # Step 2: Upload to Oracle Cloud (simulate the Mac uploader)
    print("\n☁️ STEP 2: Uploading to Oracle Cloud...")
    
    try:
        config = oci.config.from_file('~/.oci/config', 'DEFAULT')
        client = oci.object_storage.ObjectStorageClient(config)
        namespace = client.get_namespace().data
        
        object_name = f"screenshots/pipeline_test_{timestamp}.png"
        
        with open(screenshot_path, 'rb') as file_data:
            client.put_object(
                namespace_name=namespace,
                bucket_name='screenshot-bucket',
                object_name=object_name,
                put_object_body=file_data,
                content_type='image/png'
            )
        
        print(f"✅ Uploaded to Oracle Cloud: {object_name}")
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return
    
    # Step 3: Download and process with OpenAI (simulate the VM watcher)
    print("\n🤖 STEP 3: Processing with OpenAI Vision...")
    
    try:
        # Download from Oracle Cloud
        response = client.get_object(
            namespace_name=namespace,
            bucket_name='screenshot-bucket',
            object_name=object_name
        )
        
        image_data = response.data.content
        print(f"📥 Downloaded {len(image_data)} bytes from Oracle Cloud")
        
        # Encode for OpenAI
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Send to OpenAI
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
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        print("🔄 Sending to OpenAI GPT-4o...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            extracted_content = result['choices'][0]['message']['content'].strip()
            usage = result.get('usage', {})
            
            print("✅ OpenAI processing complete!")
            print(f"💰 Tokens used: {usage.get('total_tokens', 'unknown')}")
            print(f"💸 Cost: ~${usage.get('total_tokens', 0) * 0.00001:.4f}")
            
        else:
            print(f"❌ OpenAI API error: {response.status_code}")
            print(response.text)
            return
            
    except Exception as e:
        print(f"❌ Error processing with OpenAI: {e}")
        return
    
    # Step 4: Save extracted code and display results
    print("\n💾 STEP 4: Saving results...")
    
    try:
        if extracted_content == 'NO_CODE_FOUND':
            print("ℹ️ No Python code detected in the screenshot")
            result_message = "No Python code found in the captured screenshot."
        else:
            # Save as Python file
            py_filename = f"extracted_code_{timestamp}.py"
            py_filepath = Path(f"/tmp/{py_filename}")
            
            header = f"""# Extracted from screenshot: pipeline_test_{timestamp}.png
# Processed at: {datetime.now().isoformat()}
# Full Pipeline Test - Mac → Oracle Cloud → OpenAI → Result

"""
            
            with open(py_filepath, 'w', encoding='utf-8') as f:
                f.write(header + extracted_content)
            
            print(f"✅ Code saved to: {py_filepath}")
            result_message = f"Python code extracted and saved as {py_filename}"
        
    except Exception as e:
        print(f"❌ Error saving results: {e}")
        return
    
    # Step 5: Display final results
    print("\n🎉 PIPELINE TEST COMPLETE!")
    print("=" * 50)
    print("📋 SUMMARY:")
    print(f"   📸 Screenshot: {screenshot_path.name}")
    print(f"   ☁️ Oracle Cloud: {object_name}")
    print(f"   🤖 OpenAI: Processed successfully")
    print(f"   📱 Result: {result_message}")
    
    print("\n📝 EXTRACTED CONTENT:")
    print("-" * 50)
    print(extracted_content)
    print("-" * 50)
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    if screenshot_path.exists():
        screenshot_path.unlink()
        print("✅ Removed local screenshot")
    
    print("\n🎯 NEXT STEPS:")
    print("   1. This same process will run automatically on your Oracle VM")
    print("   2. Add phone notifications (ntfy/Telegram) to get results on your phone")
    print("   3. Use cursor triggers to capture screenshots on-demand")

if __name__ == "__main__":
    test_full_pipeline()
