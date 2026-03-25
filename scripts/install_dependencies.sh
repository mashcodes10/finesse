#!/bin/bash
# Installation script for Claude 4 Sonnet dependencies

echo "🚀 Installing Claude 4 Sonnet dependencies..."

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
else
    echo "⚠️  No virtual environment detected. Consider using a venv for better dependency management."
fi

# Install the updated requirements
echo "📦 Installing updated requirements..."
pip install -r requirements_vm.txt

# Check if anthropic package is installed
if python -c "import anthropic" 2>/dev/null; then
    echo "✅ Anthropic package installed successfully"
else
    echo "❌ Failed to install anthropic package"
    exit 1
fi

# Check if openai package is still installed (should be removed)
if python -c "import openai" 2>/dev/null; then
    echo "⚠️  OpenAI package is still installed. You may want to uninstall it: pip uninstall openai"
else
    echo "✅ OpenAI package is not installed (as expected)"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "📝 Next steps:"
echo "1. Set your Anthropic API key: export ANTHROPIC_API_KEY='your-key-here'"
echo "2. Test the integration: python test_claude_integration.py"
echo "3. Run the screenshot watcher: python screenshot_watcher.py"
echo ""
echo "🔑 Get your Anthropic API key from: https://console.anthropic.com/"
