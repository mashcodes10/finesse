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

def test_claude_initialization():
    """Test if Claude client initializes properly"""
    print("\n🧪 Testing Claude initialization...")
    
    # Check if API key is set
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        print("Please set your Anthropic API key: export ANTHROPIC_API_KEY='your-key-here'")
        return False
    
    print("✅ ANTHROPIC_API_KEY is set")
    
    try:
        # Try to create a watcher instance (this will test Claude initialization)
        watcher = ScreenshotWatcher()
        print("✅ Claude client initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize Claude client: {e}")
        return False

def test_claude_api_connection():
    """Test if we can make a simple API call to Claude"""
    print("\n🧪 Testing Claude API connection...")
    
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # Make a simple test call
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": "Hello! Please respond with 'Claude is working!' if you can see this message."
                }
            ]
        )
        
        print(f"✅ Claude API connection successful")
        print(f"Response: {response.content[0].text}")
        return True
        
    except Exception as e:
        print(f"❌ Claude API connection failed: {e}")
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
    print("🚀 Testing Claude 4 Sonnet Integration")
    print("=" * 50)
    
    # Test 1: Import and initialization
    init_success = test_claude_initialization()
    
    # Test 2: API connection
    api_success = test_claude_api_connection()
    
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
