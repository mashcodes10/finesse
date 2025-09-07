#!/usr/bin/env python3
"""
Mac Screenshot Uploader - Cursor Triggered
Takes silent screenshots when mouse cursor is moved to a trigger zone and uploads to Oracle Cloud Object Storage
"""

import os
import subprocess
import time
import datetime
import oci
import logging
from pathlib import Path

# Import these only when needed to avoid GUI popup
try:
    import Quartz
    from Cocoa import NSEvent, NSScreen, NSApplication
    COCOA_AVAILABLE = True
except ImportError:
    COCOA_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/screenshot_uploader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ScreenshotUploader:
    def __init__(self):
        # Oracle Cloud Configuration
        self.config = oci.config.from_file("~/.oci/config", "DEFAULT")
        self.object_storage = oci.object_storage.ObjectStorageClient(self.config)
        
        # Get the namespace
        self.namespace = self.object_storage.get_namespace().data
        
        # Configuration - Update these values
        self.bucket_name = "screenshot-bucket"
        self.screenshot_dir = Path.home() / "Screenshots" / "auto_screenshots"
        
        # Create screenshot directory if it doesn't exist
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Cursor trigger configuration
        self.trigger_zones = self._setup_trigger_zones()
        self.last_trigger_time = 0
        self.cooldown_seconds = 2  # Minimum time between screenshots
        self.cursor_hold_time = 1.0  # How long cursor must stay in zone
        self.cursor_enter_time = None
        
        logger.info(f"Initialized ScreenshotUploader with bucket: {self.bucket_name}")
        logger.info(f"Screenshot directory: {self.screenshot_dir}")
        logger.info(f"Trigger zones configured: {len(self.trigger_zones)} zones")

    def _setup_trigger_zones(self):
        """Setup cursor trigger zones on the screen"""
        # Get screen dimensions using Quartz to avoid NSApplication
        try:
            if not COCOA_AVAILABLE:
                logger.error("Cocoa framework not available")
                return []
                
            # Get main display dimensions
            main_display = Quartz.CGMainDisplayID()
            width = Quartz.CGDisplayPixelsWide(main_display)
            height = Quartz.CGDisplayPixelsHigh(main_display)
        except Exception as e:
            logger.error(f"Error getting screen dimensions: {e}")
            # Fallback to common resolution
            width, height = 1920, 1080
        
        # Define trigger zones - you can customize these
        zones = [
            # Top-left corner (100x100 pixels) 
            {
                'name': 'top-left-corner',
                'x1': 0, 'y1': 0,
                'x2': 100, 'y2': 100,
                'description': 'Top-left corner (100x100)'
            },
            # Bottom-left corner (100x100 pixels)
            {
                'name': 'bottom-left-corner',
                'x1': 0, 'y1': height - 100,
                'x2': 100, 'y2': height,
                'description': 'Bottom-left corner (100x100)'
            }
        ]
        
        logger.info(f"Screen dimensions: {width}x{height}")
        for zone in zones:
            logger.info(f"Trigger zone '{zone['name']}': {zone['description']} at ({zone['x1']:.0f},{zone['y1']:.0f}) to ({zone['x2']:.0f},{zone['y2']:.0f})")
        
        return zones

    def get_cursor_position(self):
        """Get current cursor position"""
        try:
            if not COCOA_AVAILABLE:
                logger.error("Cocoa framework not available")
                return None, None
                
            # Use Quartz directly to avoid NSApplication issues
            event = Quartz.CGEventCreate(None)
            point = Quartz.CGEventGetLocation(event)
            return point.x, point.y
        except Exception as e:
            logger.error(f"Error getting cursor position: {e}")
            return None, None

    def is_cursor_in_trigger_zone(self):
        """Check if cursor is in any trigger zone"""
        x, y = self.get_cursor_position()
        if x is None or y is None:
            return False, None
            
        for zone in self.trigger_zones:
            if (zone['x1'] <= x <= zone['x2'] and 
                zone['y1'] <= y <= zone['y2']):
                return True, zone['name']
        
        return False, None

    def should_take_screenshot(self):
        """Determine if screenshot should be taken based on cursor position and timing"""
        current_time = time.time()
        
        # Check cooldown period
        if current_time - self.last_trigger_time < self.cooldown_seconds:
            return False, "cooldown"
        
        # Check if cursor is in trigger zone
        in_zone, zone_name = self.is_cursor_in_trigger_zone()
        
        if in_zone:
            if self.cursor_enter_time is None:
                # Cursor just entered trigger zone
                self.cursor_enter_time = current_time
                logger.debug(f"Cursor entered trigger zone: {zone_name}")
                return False, "hold_time"
            elif current_time - self.cursor_enter_time >= self.cursor_hold_time:
                # Cursor has been in zone long enough
                self.cursor_enter_time = None  # Reset
                self.last_trigger_time = current_time
                logger.info(f"Screenshot triggered by cursor in zone: {zone_name}")
                return True, zone_name
            else:
                # Still waiting for hold time
                return False, "hold_time"
        else:
            # Cursor not in trigger zone
            self.cursor_enter_time = None
            return False, "not_in_zone"

    def take_screenshot(self):
        """Take a silent screenshot using macOS screencapture command"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = self.screenshot_dir / filename
            
            # Use screencapture with silent flag
            result = subprocess.run([
                "screencapture", 
                "-x",  # Silent mode (no sound)
                "-t", "png",  # PNG format
                str(filepath)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Screenshot taken: {filename}")
                return filepath
            else:
                logger.error(f"Screenshot failed: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None

    def upload_to_oracle_cloud(self, filepath):
        """Upload screenshot to Oracle Cloud Object Storage"""
        try:
            object_name = f"screenshots/{filepath.name}"
            
            with open(filepath, 'rb') as file_data:
                self.object_storage.put_object(
                    namespace_name=self.namespace,
                    bucket_name=self.bucket_name,
                    object_name=object_name,
                    put_object_body=file_data,
                    content_type='image/png'
                )
            
            logger.info(f"Uploaded {filepath.name} to Oracle Cloud Storage")
            
            # Optional: Remove local file after successful upload
            filepath.unlink()
            logger.info(f"Removed local file: {filepath.name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error uploading to Oracle Cloud: {e}")
            return False

    def run_cursor_triggered(self, check_interval=0.1):
        """Run the cursor-triggered screenshot uploader"""
        logger.info("Starting cursor-triggered screenshot capture")
        logger.info("📍 Trigger zones:")
        for zone in self.trigger_zones:
            logger.info(f"   • {zone['description']}")
        logger.info(f"⏱️  Hold cursor in trigger zone for {self.cursor_hold_time}s to capture")
        logger.info(f"🔄 Cooldown period: {self.cooldown_seconds}s between screenshots")
        logger.info("🖱️  Move your cursor to any trigger zone to take a screenshot!")
        
        while True:
            try:
                # Check if screenshot should be taken
                should_capture, reason = self.should_take_screenshot()
                
                if should_capture:
                    # Take screenshot
                    filepath = self.take_screenshot()
                    
                    if filepath and filepath.exists():
                        # Upload to Oracle Cloud
                        success = self.upload_to_oracle_cloud(filepath)
                        
                        if success:
                            logger.info(f"✅ Screenshot cycle completed successfully (triggered by {reason})")
                        else:
                            logger.error("❌ Failed to upload screenshot")
                    else:
                        logger.error("❌ No screenshot file to upload")
                
                # Small delay to prevent high CPU usage
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("Screenshot uploader stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(1)  # Wait 1 second before retrying

    def run_continuous(self, interval_minutes=5):
        """Run the screenshot uploader continuously (timer-based mode)"""
        interval_seconds = interval_minutes * 60
        logger.info(f"Starting timer-based screenshot capture every {interval_minutes} minutes")
        
        while True:
            try:
                # Take screenshot
                filepath = self.take_screenshot()
                
                if filepath and filepath.exists():
                    # Upload to Oracle Cloud
                    success = self.upload_to_oracle_cloud(filepath)
                    
                    if success:
                        logger.info("Screenshot cycle completed successfully")
                    else:
                        logger.error("Failed to upload screenshot")
                else:
                    logger.error("No screenshot file to upload")
                
                # Wait for next interval
                logger.info(f"Waiting {interval_minutes} minutes until next screenshot...")
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Screenshot uploader stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

def test_cursor_zones():
    """Test mode to help visualize cursor zones without taking screenshots"""
    print("🧪 Testing cursor zones (no screenshots will be taken)")
    print("Move your cursor around to see zone detection...")
    print("Press Ctrl+C to stop\n")
    
    try:
        uploader = ScreenshotUploader()
        last_zone = None
        
        while True:
            x, y = uploader.get_cursor_position()
            in_zone, zone_name = uploader.is_cursor_in_trigger_zone()
            
            if in_zone and zone_name != last_zone:
                print(f"✅ Cursor ENTERED zone: {zone_name} at ({x:.0f}, {y:.0f})")
                last_zone = zone_name
            elif not in_zone and last_zone is not None:
                print(f"❌ Cursor LEFT zone: {last_zone}")
                last_zone = None
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n🧪 Test mode stopped")
    except Exception as e:
        print(f"❌ Test failed: {e}")

def main():
    """Main function"""
    import sys
    
    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode to see cursor zone detection
        test_cursor_zones()
    elif len(sys.argv) > 1 and sys.argv[1] == "--timer":
        # Use the old timer-based mode
        try:
            uploader = ScreenshotUploader()
            interval_minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            uploader.run_continuous(interval_minutes=interval_minutes)
        except Exception as e:
            logger.error(f"Failed to start timer-based screenshot uploader: {e}")
            print("Make sure you have configured Oracle Cloud CLI and have proper permissions.")
    else:
        # Use the new cursor-triggered mode (default)
        try:
            uploader = ScreenshotUploader()
            uploader.run_cursor_triggered()
        except Exception as e:
            logger.error(f"Failed to start cursor-triggered screenshot uploader: {e}")
            print("Make sure you have configured Oracle Cloud CLI and have proper permissions.")
            print("\nAvailable modes:")
            print("  python3 mac_screenshot_uploader.py           # Cursor-triggered mode")
            print("  python3 mac_screenshot_uploader.py --test    # Test cursor zones")
            print("  python3 mac_screenshot_uploader.py --timer 5 # Timer-based mode")

if __name__ == "__main__":
    main()
