#!/usr/bin/env python3
"""
Test the GPT-4o vision fix with actual screenshot
"""

import oci
import base64
import requests
import os

def test_vision_with_screenshot():
    """Test GPT-4o with an actual screenshot from your bucket"""
    
    # You'll need to set this
    api_key = input("Enter your OpenAI API key: ").strip()
    if not api_key:
        print("❌ No API key provided")
        return
    
    try:
        # Get a screenshot from your bucket
        print("📥 Downloading a screenshot from Oracle Cloud...")
        config = oci.config.from_file('~/.oci/config', 'DEFAULT')
        client = oci.object_storage.ObjectStorageClient(config)
        namespace = client.get_namespace().data
        
        # Get latest screenshot
        response = client.list_objects(
            namespace_name=namespace,
            bucket_name='screenshot-bucket',
            prefix='screenshots/',
            limit=1
        )
        
        if not response.data.objects:
            print("❌ No screenshots found in bucket")
            return
            
        latest_screenshot = response.data.objects[0].name
        print(f"📷 Using screenshot: {latest_screenshot}")
        
        # Download screenshot
        obj_response = client.get_object(
            namespace_name=namespace,
            bucket_name='screenshot-bucket',
            object_name=latest_screenshot
        )
        
        image_data = obj_response.data.content
        print(f"✅ Downloaded {len(image_data)} bytes")
        
        # Encode to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Test with GPT-4o
        print("🤖 Testing GPT-4o vision...")
        
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
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            extracted_text = result['choices'][0]['message']['content'].strip()
            usage = result.get('usage', {})
            
            print("✅ GPT-4o Vision API works!")
            print(f"💰 Tokens used: {usage.get('total_tokens', 'unknown')}")
            print(f"💸 Estimated cost: ~${usage.get('total_tokens', 0) * 0.00001:.4f}")
            print("\n📝 Extracted content:")
            print("-" * 50)
            print(extracted_text)
            print("-" * 50)
            
            if extracted_text == 'NO_CODE_FOUND':
                print("\n💡 No Python code detected in this screenshot")
            else:
                print("\n🎉 Python code extraction successful!")
                
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 Testing GPT-4o Vision Fix")
    print("=" * 40)
    test_vision_with_screenshot()
