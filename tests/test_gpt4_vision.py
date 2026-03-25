#!/usr/bin/env python3
"""
Test GPT-4 Vision Access
Quick test to verify if GPT-4 Vision API works with your account
"""

import os
import requests
import base64
import json

def test_gpt4_vision():
    """Test GPT-4 Vision API with a simple image"""
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return False
    
    print("🧪 Testing GPT-4 Vision API access...")
    
    # Create a simple test image (base64 encoded small PNG)
    # This is a tiny 1x1 pixel transparent PNG for testing
    test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    
    # Test payload for GPT-4 Vision
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What do you see in this image? Just say 'Test successful' if you can process this."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{test_image_b64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 50
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        print("📡 Sending test request to GPT-4 Vision...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✅ GPT-4 Vision API works!")
            print(f"📝 Response: {content}")
            print(f"💰 Tokens used: {result.get('usage', {}).get('total_tokens', 'unknown')}")
            return True
            
        elif response.status_code == 401:
            print("❌ Invalid API key")
            return False
            
        elif response.status_code == 429:
            print("⚠️ Rate limit exceeded - try again in a moment")
            return False
            
        elif response.status_code == 403:
            print("❌ Access denied - you need GPT-4 Vision access")
            print("💡 Solution: Upgrade to a paid OpenAI account")
            print("   Visit: https://platform.openai.com/settings/organization/billing")
            return False
            
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ Request timed out - API might be slow")
        return False
        
    except Exception as e:
        print(f"❌ Error testing GPT-4 Vision: {e}")
        return False

def check_account_status():
    """Check OpenAI account status and available models"""
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    print("\n🔍 Checking account status...")
    
    try:
        # Check available models
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get("https://api.openai.com/v1/models", headers=headers)
        
        if response.status_code == 200:
            models = response.json()
            
            # Look for GPT-4 models
            gpt4_models = [m['id'] for m in models.get('data', []) if 'gpt-4' in m.get('id', '')]
            vision_models = [m['id'] for m in models.get('data', []) if 'vision' in m.get('id', '')]
            
            print(f"✅ Account active with {len(models.get('data', []))} available models")
            print(f"🤖 GPT-4 models: {len(gpt4_models)}")
            print(f"👁️ Vision models: {len(vision_models)}")
            
            if vision_models:
                print(f"Available vision models: {vision_models}")
            else:
                print("⚠️ No vision models found - you need a paid account for GPT-4 Vision")
                
        else:
            print(f"❌ Error checking models: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error checking account: {e}")

if __name__ == "__main__":
    print("🔬 OpenAI GPT-4 Vision Test")
    print("=" * 40)
    
    # Check account status first
    check_account_status()
    
    # Test GPT-4 Vision
    print("\n" + "=" * 40)
    success = test_gpt4_vision()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 GPT-4 Vision is working! You can use the full OpenAI integration.")
        print("📋 Next step: Run the screenshot_watcher.py on your Oracle VM")
    else:
        print("⚠️ GPT-4 Vision not available. Options:")
        print("   1. Upgrade to paid OpenAI account (recommended)")
        print("   2. Use alternative_vision_watcher.py (limited OCR)")
        print("   3. Set up Google Cloud Vision or Azure Computer Vision")
