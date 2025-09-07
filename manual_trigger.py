#!/usr/bin/env python3
"""
Manual Screenshot Trigger
For testing the screenshot system without cursor detection
"""

import os
import subprocess
import datetime
import oci
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def manual_screenshot():
    """Take a manual screenshot and upload it"""
    try:
        # Oracle Cloud Configuration
        config = oci.config.from_file("~/.oci/config", "DEFAULT")
        object_storage = oci.object_storage.ObjectStorageClient(config)
        namespace = object_storage.get_namespace().data
        
        # Configuration
        bucket_name = "screenshot-bucket"
        screenshot_dir = Path.home() / "Screenshots" / "auto_screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Take screenshot
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_screenshot_{timestamp}.png"
        filepath = screenshot_dir / filename
        
        print(f"📸 Taking screenshot: {filename}")
        
        result = subprocess.run([
            "screencapture", 
            "-x",  # Silent mode
            "-t", "png",
            str(filepath)
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Screenshot taken: {filename}")
            
            # Upload to Oracle Cloud
            object_name = f"screenshots/{filename}"
            
            with open(filepath, 'rb') as file_data:
                object_storage.put_object(
                    namespace_name=namespace,
                    bucket_name=bucket_name,
                    object_name=object_name,
                    put_object_body=file_data,
                    content_type='image/png'
                )
            
            print(f"☁️  Uploaded to Oracle Cloud: {object_name}")
            
            # Clean up local file
            filepath.unlink()
            print(f"🗑️  Removed local file")
            
            print(f"🎉 Manual screenshot completed successfully!")
            return True
            
        else:
            print(f"❌ Screenshot failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Manual Screenshot Trigger")
    print("=" * 40)
    manual_screenshot()
