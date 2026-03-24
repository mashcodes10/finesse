#!/usr/bin/env python3
"""
Silent Mac Screenshot Daemon - Cursor Triggered
Runs as a background daemon without GUI elements
"""

import os
import sys
import subprocess
import time
import datetime
import threading
import oci
import logging
from pathlib import Path
import signal

RESPONSE_OBJECT   = "responses/latest_response.txt"
LOCAL_RESPONSE    = "/tmp/finesse_latest_response.txt"
RESPONSE_POLL_SEC = 5   # How often to check Oracle Cloud for a new response

# Configure logging for daemon mode
log_file = '/tmp/screenshot_daemon.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        # Remove console handler for true background operation
    ]
)
logger = logging.getLogger(__name__)

class SilentScreenshotDaemon:
    def __init__(self):
        # Oracle Cloud Configuration
        self.config = oci.config.from_file("~/.oci/config", "DEFAULT")
        self.object_storage = oci.object_storage.ObjectStorageClient(self.config)
        
        # Get the namespace
        self.namespace = self.object_storage.get_namespace().data
        
        # Configuration
        self.bucket_name = "screenshot-bucket"
        self.upload_folder = "quiz-screenshots/"   # Folder watched by quiz_answer_watcher.py
        self.screenshot_dir = Path.home() / "Screenshots" / "auto_screenshots"
        
        # Create screenshot directory if it doesn't exist
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Trigger zones for your screen (adjust these coordinates)
        self.trigger_zones = [
            {'name': 'top-left', 'x1': 0, 'y1': 0, 'x2': 100, 'y2': 100},
            {'name': 'bottom-left', 'x1': 0, 'y1': 1012, 'x2': 100, 'y2': 1112}
        ]
        
        # Timing configuration
        self.last_trigger_time = 0
        self.cooldown_seconds = 3
        self.check_interval = 0.5  # Check every 500ms instead of 100ms
        
        # PID file for daemon management
        self.pid_file = '/tmp/screenshot_daemon.pid'
        
        logger.info(f"Silent screenshot daemon initialized")
        logger.info(f"Bucket: {self.bucket_name}")
        logger.info(f"Upload folder: {self.upload_folder}")
        logger.info(f"Trigger zones: {self.trigger_zones}")

    def get_cursor_position(self):
        """Get cursor position using system command - no GUI popup"""
        try:
            # Method 1: Use cliclick if available
            if self._check_cliclick():
                result = subprocess.run(['cliclick', 'p'], capture_output=True, text=True)
                if result.returncode == 0:
                    coords = result.stdout.strip().split(',')
                    return float(coords[0]), float(coords[1])
            
            # Method 2: Use Python with Quartz (requires import but should be silent)
            try:
                import Quartz
                event = Quartz.CGEventCreate(None)
                if event:
                    point = Quartz.CGEventGetLocation(event)
                    return point.x, point.y
            except:
                pass
            
            # Method 3: Corrected AppleScript
            script = '''
            tell application "System Events"
                return (mouse position) as string
            end tell
            '''
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            if result.returncode == 0:
                # Parse "x, y" format
                coords_str = result.stdout.strip()
                coords = coords_str.split(', ')
                if len(coords) == 2:
                    return float(coords[0]), float(coords[1])
                
        except Exception as e:
            logger.debug(f"Error getting cursor position: {e}")
            
        return None, None

    def _check_cliclick(self):
        """Check if cliclick is installed"""
        try:
            subprocess.run(['cliclick'], capture_output=True)
            return True
        except FileNotFoundError:
            return False

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
        """Simple trigger logic - take screenshot if in zone and cooldown passed"""
        current_time = time.time()
        
        # Check cooldown period
        if current_time - self.last_trigger_time < self.cooldown_seconds:
            return False, "cooldown"
        
        # Check if cursor is in trigger zone
        in_zone, zone_name = self.is_cursor_in_trigger_zone()
        
        if in_zone:
            self.last_trigger_time = current_time
            return True, zone_name
        
        return False, "not_in_zone"

    def take_screenshot(self):
        """Take a screenshot"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = self.screenshot_dir / filename
            
            # Take screenshot
            result = subprocess.run([
                "screencapture", 
                "-x",  # Silent mode
                "-t", "png",
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
        """Upload screenshot to Oracle Cloud"""
        try:
            object_name = f"{self.upload_folder}{filepath.name}"
            
            with open(filepath, 'rb') as file_data:
                self.object_storage.put_object(
                    namespace_name=self.namespace,
                    bucket_name=self.bucket_name,
                    object_name=object_name,
                    put_object_body=file_data,
                    content_type='image/png'
                )
            
            logger.info(f"Uploaded {filepath.name} to Oracle Cloud in folder: {self.upload_folder}")
            
            # Remove local file
            filepath.unlink()
            logger.info(f"Removed local file: {filepath.name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error uploading to Oracle Cloud: {e}")
            return False

    def write_pid_file(self):
        """Write PID file for daemon management"""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            logger.error(f"Error writing PID file: {e}")

    def remove_pid_file(self):
        """Remove PID file"""
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down daemon")
        self.remove_pid_file()
        sys.exit(0)

    # ── Response syncer ───────────────────────────────────────────────────────

    def _response_sync_loop(self):
        """
        Background thread: polls Oracle Cloud every RESPONSE_POLL_SEC seconds
        for responses/latest_response.txt and saves it locally so overlay_display.py
        can read it without needing cloud credentials.
        """
        last_etag = None
        while True:
            try:
                head = self.object_storage.head_object(
                    namespace_name=self.namespace,
                    bucket_name=self.bucket_name,
                    object_name=RESPONSE_OBJECT
                )
                etag = head.headers.get('etag', '')
                if etag != last_etag:
                    resp = self.object_storage.get_object(
                        namespace_name=self.namespace,
                        bucket_name=self.bucket_name,
                        object_name=RESPONSE_OBJECT
                    )
                    content = resp.data.content
                    if isinstance(content, bytes):
                        content = content.decode('utf-8')
                    Path(LOCAL_RESPONSE).write_text(content, encoding='utf-8')
                    last_etag = etag
                    logger.info(f"Response synced → {LOCAL_RESPONSE}")
            except Exception:
                # Object may not exist yet — that's fine, keep polling silently
                pass
            time.sleep(RESPONSE_POLL_SEC)

    def run_daemon(self):
        """Run the daemon"""
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Write PID file
        self.write_pid_file()

        # Start response syncer in background thread
        sync_thread = threading.Thread(target=self._response_sync_loop, daemon=True)
        sync_thread.start()
        logger.info(f"Response syncer started — polling every {RESPONSE_POLL_SEC}s for {RESPONSE_OBJECT}")

        logger.info("Silent screenshot daemon started")
        logger.info(f"PID: {os.getpid()}")
        logger.info(f"Log file: {log_file}")
        logger.info("Monitoring cursor for trigger zones...")
        
        try:
            while True:
                # Check if screenshot should be taken
                should_capture, reason = self.should_take_screenshot()
                
                if should_capture:
                    logger.info(f"Screenshot triggered by zone: {reason}")
                    
                    # Take screenshot
                    filepath = self.take_screenshot()
                    
                    if filepath and filepath.exists():
                        # Upload to Oracle Cloud
                        success = self.upload_to_oracle_cloud(filepath)
                        
                        if success:
                            logger.info(f"Screenshot cycle completed (zone: {reason})")
                        else:
                            logger.error("Failed to upload screenshot")
                
                # Sleep to prevent high CPU usage
                time.sleep(self.check_interval)
                
        except Exception as e:
            logger.error(f"Daemon error: {e}")
        finally:
            self.remove_pid_file()

def start_daemon():
    """Start the daemon"""
    daemon = SilentScreenshotDaemon()
    daemon.run_daemon()

def stop_daemon():
    """Stop the daemon"""
    pid_file = '/tmp/screenshot_daemon.pid'
    try:
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped screenshot daemon (PID: {pid})")
            
            # Wait a moment and check if it's really stopped
            time.sleep(1)
            if os.path.exists(pid_file):
                os.remove(pid_file)
        else:
            print("Screenshot daemon is not running")
    except Exception as e:
        print(f"Error stopping daemon: {e}")

def status_daemon():
    """Check daemon status"""
    pid_file = '/tmp/screenshot_daemon.pid'
    log_file = '/tmp/screenshot_daemon.log'
    
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            try:
                os.kill(pid, 0)  # Signal 0 just checks if process exists
                print(f"✅ Screenshot daemon is running (PID: {pid})")
                print(f"📄 Log file: {log_file}")
                print(f"🖱️  Trigger zones: top-left and bottom-left corners")
                
                # Show recent log entries
                if os.path.exists(log_file):
                    print("\n📝 Recent log entries:")
                    subprocess.run(['tail', '-5', log_file])
                
            except OSError:
                print("❌ Screenshot daemon PID file exists but process is not running")
                os.remove(pid_file)
        except Exception as e:
            print(f"Error checking daemon status: {e}")
    else:
        print("❌ Screenshot daemon is not running")

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 mac_screenshot_daemon.py start   # Start daemon")
        print("  python3 mac_screenshot_daemon.py stop    # Stop daemon") 
        print("  python3 mac_screenshot_daemon.py status  # Check status")
        print("  python3 mac_screenshot_daemon.py restart # Restart daemon")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "start":
        start_daemon()
    elif command == "stop":
        stop_daemon()
    elif command == "status":
        status_daemon()
    elif command == "restart":
        stop_daemon()
        time.sleep(2)
        start_daemon()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
