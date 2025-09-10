#!/usr/bin/env python3
"""
Create a test Python problem screenshot for testing the vision assistant
"""

from PIL import Image, ImageDraw, ImageFont
import io
import base64

def create_problem_screenshot():
    """Create a screenshot with a Python problem"""
    
    # Create image
    width, height = 800, 600
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # Try to use a system font, fallback to default
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 24)
        font_medium = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 18)
        font_small = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 14)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Draw problem text
    y = 30
    
    # Title
    draw.text((30, y), "Python Problem - Fix the Failing Code", fill='black', font=font_large)
    y += 60
    
    # Problem description
    problem_text = """
Problem: Write a function that calculates the factorial of a number.

Current code (FAILING):
def factorial(n):
    if n == 0:
        return 0  # BUG: Should return 1
    return n * factorial(n - 1)

Test cases:
assert factorial(0) == 1  # FAILS
assert factorial(5) == 120  # FAILS due to base case
assert factorial(1) == 1   # FAILS

Fix the code to make all tests pass.
    """.strip()
    
    lines = problem_text.split('\n')
    for line in lines:
        if line.strip():
            if line.startswith('def ') or line.startswith('    '):
                # Code lines
                draw.text((50, y), line, fill='blue', font=font_medium)
            elif line.startswith('assert'):
                # Test lines
                draw.text((50, y), line, fill='red', font=font_medium)
            elif 'BUG:' in line:
                # Bug comment
                draw.text((50, y), line, fill='red', font=font_small)
            else:
                # Regular text
                draw.text((50, y), line, fill='black', font=font_medium)
        y += 25
    
    # Save image
    image.save('/tmp/test_python_problem.png')
    print("✅ Created test problem screenshot: /tmp/test_python_problem.png")
    
    # Convert to base64 for API testing
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    image_data = buffer.getvalue()
    base64_image = base64.b64encode(image_data).decode('utf-8')
    
    return base64_image, image_data

def test_problem_solving():
    """Test the problem-solving prompt with the created image"""
    import requests
    
    api_key = input("Enter your OpenAI API key: ").strip()
    if not api_key:
        print("❌ No API key provided")
        return
    
    print("🎨 Creating test Python problem screenshot...")
    base64_image, image_data = create_problem_screenshot()
    
    print("🤖 Testing problem-solving prompt...")
    
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
        "max_tokens": 1000
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            solution = result['choices'][0]['message']['content'].strip()
            usage = result.get('usage', {})
            
            print("✅ Problem-solving test successful!")
            print(f"💰 Tokens used: {usage.get('total_tokens', 'unknown')}")
            
            print("\n📋 PROBLEM:")
            print("Fix the factorial function to pass all tests")
            
            print("\n🔧 AI SOLUTION:")
            print("-" * 60)
            print(solution)
            print("-" * 60)
            
            # Test the solution
            print("\n🧪 Testing the AI solution...")
            try:
                # Execute the solution
                exec(solution)
                print("✅ Code executed successfully!")
            except Exception as e:
                print(f"❌ Code execution failed: {e}")
                
        else:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 Python Problem-Solving Test")
    print("=" * 50)
    test_problem_solving()
