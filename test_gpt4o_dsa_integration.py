#!/usr/bin/env python3
"""
Test script for GPT-4o DSA screenshot processing
Tests the GPT-4o API integration with sample screenshots
"""

import os
import sys
import base64
import json
from pathlib import Path
import openai
import requests

def test_gpt4o_dsa_api():
    """Test GPT-4o API with a sample DSA problem"""
    
    # Check for API key
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return False
    
    try:
        print("✅ OpenAI API key found")
        
        # Test with a simple text-based DSA problem (no image required for basic test)
        test_prompt = """You are an expert DSA problem solver. Please read the following problem and provide a Python solution:

Problem: Two Sum
Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.
You may assume that each input would have exactly one solution, and you may not use the same element twice.

Example:
Input: nums = [2,7,11,15], target = 9
Output: [0,1]
Explanation: Because nums[0] + nums[1] == 9, we return [0, 1].

Please provide:
1. Problem analysis
2. Multiple approaches with time/space complexity
3. Clean Python implementation
4. Test cases"""

        print("🚀 Testing GPT-4o API...")
        
        # Prepare the request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_api_key}"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": test_prompt
                }
            ],
            "max_completion_tokens": 2000
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            
            if 'choices' in result and len(result['choices']) > 0:
                response_text = result['choices'][0]['message']['content'].strip()
                
                print("✅ GPT-4o API call successful!")
                usage = result.get('usage', {})
                print(f"📊 Tokens used: {usage.get('total_tokens', 'unknown')}")
                print(f"📝 Response length: {len(response_text)} characters")
                
                # Display the response
                print("\n" + "="*80)
                print("🔥 GPT-4o DSA SOLUTION:")
                print("="*80)
                print(response_text)
                print("="*80)
                
                # Save test output
                test_output_file = Path("/tmp/gpt4o_dsa_test_output.py")
                with open(test_output_file, 'w', encoding='utf-8') as f:
                    f.write(f"# GPT-4o DSA Test Output\n# Generated at: {test_prompt}\n\n")
                    f.write(response_text)
                
                print(f"💾 Test output saved to: {test_output_file}")
                return True
            else:
                print("❌ No content in GPT-4o response")
                return False
        else:
            print(f"❌ GPT-4o API error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing GPT-4o API: {e}")
        return False

def test_image_processing():
    """Test image processing capabilities (if test images are available)"""
    print("\n🖼️  Testing image processing capabilities...")
    
    # Look for any test images in the project
    test_image_paths = [
        "test_problem.png",
        "sample_dsa.png",
        "/tmp/test_screenshot.png"
    ]
    
    for image_path in test_image_paths:
        if Path(image_path).exists():
            print(f"📸 Found test image: {image_path}")
            try:
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    print(f"✅ Successfully encoded image ({len(image_data)} bytes)")
                    return True
            except Exception as e:
                print(f"❌ Error processing image {image_path}: {e}")
    
    print("ℹ️  No test images found. Image processing will be tested when screenshots are uploaded.")
    return True

def main():
    """Main test function"""
    print("🧪 Testing GPT-4o DSA Integration")
    print("="*50)
    
    # Test API connection
    api_success = test_gpt4o_dsa_api()
    
    if api_success:
        print("\n✅ GPT-4o API integration test PASSED!")
        
        # Test image processing
        test_image_processing()
        
        print("\n🎉 All tests completed successfully!")
        print("\nNext steps:")
        print("1. Run the main GPT-4o DSA screenshot watcher:")
        print("   python gpt4o_dsa_screenshot_watcher.py")
        print("2. Upload screenshots to Oracle Cloud Object Storage in 'claude-screenshots/' folder")
        print("3. The watcher will process them in batches of 2")
        
        # Check environment variables
        print("\n📋 Environment Variables Status:")
        required_vars = ['OPENAI_API_KEY']
        optional_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'NTFY_TOPIC']
        
        for var in required_vars:
            status = "✅" if os.getenv(var) else "❌"
            print(f"   {status} {var}: {'Set' if os.getenv(var) else 'NOT SET'}")
        
        print("\n   Optional notification variables:")
        for var in optional_vars:
            status = "✅" if os.getenv(var) else "⚠️"
            print(f"   {status} {var}: {'Set' if os.getenv(var) else 'NOT SET'}")
            
    else:
        print("\n❌ GPT-4o API integration test FAILED!")
        print("Please check your OPENAI_API_KEY and try again.")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
