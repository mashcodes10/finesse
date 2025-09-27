#!/usr/bin/env python3
"""
Test script for Claude 4 Sonnet DSA screenshot processing
Tests the Claude API integration with sample screenshots
"""

import os
import sys
import base64
import json
from pathlib import Path
import anthropic

def test_claude_dsa_api():
    """Test Claude 4 Sonnet API with a sample DSA problem"""
    
    # Check for API key
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        print("Please set your Anthropic API key:")
        print("export ANTHROPIC_API_KEY='your-api-key-here'")
        return False
    
    try:
        # Initialize Claude client
        claude_client = anthropic.Anthropic(api_key=anthropic_api_key)
        print("✅ Claude client initialized successfully")
        
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

        print("🚀 Testing Claude 4 Sonnet API...")
        
        # Make API call
        message = claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": test_prompt
                }
            ]
        )
        
        # Check response
        if message.content and len(message.content) > 0:
            response_text = message.content[0].text.strip()
            
            print("✅ Claude API call successful!")
            print(f"📊 Tokens used: {message.usage.input_tokens + message.usage.output_tokens}")
            print(f"📝 Response length: {len(response_text)} characters")
            
            # Display the response
            print("\n" + "="*80)
            print("🔥 CLAUDE 4 SONNET DSA SOLUTION:")
            print("="*80)
            print(response_text)
            print("="*80)
            
            # Save test output
            test_output_file = Path("/tmp/claude_dsa_test_output.py")
            with open(test_output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Claude 4 Sonnet DSA Test Output\n# Generated at: {test_prompt}\n\n")
                f.write(response_text)
            
            print(f"💾 Test output saved to: {test_output_file}")
            return True
        else:
            print("❌ No content in Claude response")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Claude API: {e}")
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
    print("🧪 Testing Claude 4 Sonnet DSA Integration")
    print("="*50)
    
    # Test API connection
    api_success = test_claude_dsa_api()
    
    if api_success:
        print("\n✅ Claude 4 Sonnet API integration test PASSED!")
        
        # Test image processing
        test_image_processing()
        
        print("\n🎉 All tests completed successfully!")
        print("\nNext steps:")
        print("1. Run the main Claude DSA screenshot watcher:")
        print("   python claude_dsa_screenshot_watcher.py")
        print("2. Upload screenshots to Oracle Cloud Object Storage")
        print("3. The watcher will process them in batches of 3")
        
        # Check environment variables
        print("\n📋 Environment Variables Status:")
        required_vars = ['ANTHROPIC_API_KEY']
        optional_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'NTFY_TOPIC']
        
        for var in required_vars:
            status = "✅" if os.getenv(var) else "❌"
            print(f"   {status} {var}: {'Set' if os.getenv(var) else 'NOT SET'}")
        
        print("\n   Optional notification variables:")
        for var in optional_vars:
            status = "✅" if os.getenv(var) else "⚠️"
            print(f"   {status} {var}: {'Set' if os.getenv(var) else 'NOT SET'}")
            
    else:
        print("\n❌ Claude 4 Sonnet API integration test FAILED!")
        print("Please check your ANTHROPIC_API_KEY and try again.")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
