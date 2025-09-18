#!/usr/bin/env python3
"""
Test script to verify Question Answer Watcher integration
"""

import os
import sys
from pathlib import Path

# Add the current directory to the path so we can import the question_answer_watcher
sys.path.append(str(Path(__file__).parent))

try:
    from question_answer_watcher import QuestionAnswerWatcher
    print("✅ Successfully imported QuestionAnswerWatcher")
except ImportError as e:
    print(f"❌ Failed to import QuestionAnswerWatcher: {e}")
    sys.exit(1)

def test_question_watcher_initialization():
    """Test if Question Answer Watcher initializes properly"""
    print("\n🧪 Testing Question Answer Watcher initialization...")
    
    # Check if API key is set
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        return False
    
    print("✅ OPENAI_API_KEY is set")
    
    try:
        # Try to create a watcher instance (this will test OpenAI initialization)
        watcher = QuestionAnswerWatcher()
        print("✅ Question Answer Watcher initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize Question Answer Watcher: {e}")
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
                    "content": "Hello! Please respond with 'Question Answer Watcher is working!' if you can see this message."
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

def main():
    """Run all tests"""
    print("🚀 Testing Question Answer Watcher Integration")
    print("=" * 50)
    
    # Test 1: Import and initialization
    init_success = test_question_watcher_initialization()
    
    # Test 2: API connection
    api_success = test_openai_api_connection()
    
    print("\n" + "=" * 50)
    if init_success and api_success:
        print("🎉 All tests passed! Question Answer Watcher is ready to use.")
        print("\n📝 Next steps:")
        print("1. Upload question screenshots to the 'screenshots/' folder in your Oracle Cloud bucket")
        print("2. Run the watcher: python question_answer_watcher.py")
        print("3. The watcher will process 2 screenshots at a time and provide comprehensive answers")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
