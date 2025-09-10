#!/usr/bin/env python3
"""
Simple test script to test Claude API directly
"""

import anthropic
import os

def test_claude_api():
    """Test Claude API with the provided code"""
    
    # Check if API key is set
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        print("Please set your API key: export ANTHROPIC_API_KEY='your-key-here'")
        return False
    
    print("✅ API key found")
    
    try:
        client = anthropic.Anthropic(
            # defaults to os.environ.get("ANTHROPIC_API_KEY")
            api_key=api_key,
        )

        print("🧪 Testing batch API...")
        message_batch = client.messages.batches.create(
            requests=[
                {
                    "custom_id": "first-prompt-in-my-batch",
                    "params": {
                        "model": "claude-3-5-haiku-20241022",
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
        
        print("✅ Batch created successfully!")
        print(f"Batch ID: {message_batch.id}")
        print(f"Number of requests: {len(message_batch.requests)}")
        
        # Wait a moment and check status
        import time
        print("\n⏳ Waiting for batch to process...")
        time.sleep(3)
        
        # Check batch status
        batch_status = client.messages.batches.retrieve(message_batch.id)
        print(f"Batch Status: {batch_status.status}")
        
        if batch_status.status == "completed":
            print("🎉 Batch completed successfully!")
            # Print results if available
            if hasattr(batch_status, 'responses') and batch_status.responses:
                for i, response in enumerate(batch_status.responses):
                    print(f"\nResponse {i+1} ({response.custom_id}):")
                    if hasattr(response, 'response') and response.response:
                        print(f"Content: {response.response.content[0].text}")
            else:
                print("No responses available yet")
        elif batch_status.status == "failed":
            print("❌ Batch failed")
            if hasattr(batch_status, 'errors') and batch_status.errors:
                for error in batch_status.errors:
                    print(f"Error: {error}")
        else:
            print(f"⏳ Batch still processing (status: {batch_status.status})")
            print("You can check the status later with the batch ID")
        
        return True
        
    except Exception as e:
        print(f"❌ API call failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Claude API Directly")
    print("=" * 40)
    
    success = test_claude_api()
    
    if success:
        print("\n🎉 API test completed!")
    else:
        print("\n❌ API test failed!")
