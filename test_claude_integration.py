#!/usr/bin/env python3
"""
Test script to verify Claude 4 Sonnet integration
"""

import os
import sys
import base64
from pathlib import Path

# Add the current directory to the path so we can import the screenshot_watcher
sys.path.append(str(Path(__file__).parent))

try:
    from screenshot_watcher import ScreenshotWatcher
    print("✅ Successfully imported ScreenshotWatcher")
except ImportError as e:
    print(f"❌ Failed to import ScreenshotWatcher: {e}")
    sys.exit(1)

def test_openai_initialization():
    """Test if OpenAI client initializes properly"""
    print("\n🧪 Testing OpenAI initialization...")
    
    # Check if API key is set
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        return False
    
    print("✅ OPENAI_API_KEY is set")
    
    try:
        # Try to create a watcher instance (this will test OpenAI initialization)
        watcher = ScreenshotWatcher()
        print("✅ OpenAI client initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize OpenAI client: {e}")
        return False

def test_openai_api_connection():
    """Test if we can make a simple API call to OpenAI"""
    print("\n🧪 Testing OpenAI API connection...")
    
    try:
        import openai
        import requests
        
        # Make a simple test call
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
        }
        
        payload = {
            "model": "gpt-5",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello! Please respond with 'GPT-5 is working!' if you can see this message."
                }
            ],
            "max_completion_tokens": 100
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content'].strip()
            print(f"✅ OpenAI API connection successful")
            print(f"Response: {answer}")
            return True
        else:
            print(f"❌ OpenAI API error: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ OpenAI API connection failed: {e}")
        return False

def test_claude_batch_api():
    """Test Claude batch API functionality"""
    print("\n🧪 Testing Claude batch API...")
    
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # Test batch API as provided by user
        message_batch = client.messages.batches.create(
            requests=[
                {
                    "custom_id": "first-prompt-in-my-batch",
                    "params": {
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 100,
                        "messages": [
                            {
                                "role": "user",
                                "content": "Hey Claude, tell me a short fun fact about video games!",
                            }
                        ],
                    },
                },
                {
                    "custom_id": "second-prompt-in-my-batch",
                    "params": {
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 100,
                        "messages": [
                            {
                                "role": "user",
                                "content": "Hey Claude, tell me a short fun fact about bees!",
                            }
                        ],
                    },
                },
            ]
        )
        
        print(f"✅ Claude batch API connection successful")
        print(f"Batch ID: {message_batch.id}")
        print(f"Batch Status: {message_batch.status}")
        print(f"Number of requests: {len(message_batch.requests)}")
        
        # Wait a moment for processing
        import time
        time.sleep(2)
        
        # Check batch status
        batch_status = client.messages.batches.retrieve(message_batch.id)
        print(f"Updated Status: {batch_status.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Claude batch API connection failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing GPT-5 Thinking Integration")
    print("=" * 50)
    
    # Test 1: Import and initialization
    init_success = test_openai_initialization()
    
    # Test 2: API connection
    api_success = test_openai_api_connection()
    
    # Test 3: Batch API connection
    batch_success = test_claude_batch_api()
    
    print("\n" + "=" * 50)
    if init_success and api_success and batch_success:
        print("🎉 All tests passed! Claude 4 Sonnet integration is working correctly.")
        print("\n📝 Next steps:")
        print("1. Install the updated requirements: pip install -r requirements_vm.txt")
        print("2. Set your ANTHROPIC_API_KEY environment variable")
        print("3. Run the screenshot watcher: python screenshot_watcher.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
