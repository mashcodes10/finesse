#!/usr/bin/env python3
"""
Reset Screenshot Watcher State
Marks all existing screenshots as "already processed" so the watcher 
only processes newly captured screenshots going forward.
"""

import oci
import json
from datetime import datetime
from pathlib import Path
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner

def reset_watcher_state():
    """Mark all existing screenshots as processed"""
    
    print("🔄 Resetting screenshot watcher state...")
    print("This will mark all existing screenshots as 'already processed'")
    print("so the watcher only processes NEW screenshots going forward.")
    print()
    
    try:
        # Initialize Oracle Cloud client
        signer = InstancePrincipalsSecurityTokenSigner()
        object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
        namespace = object_storage.get_namespace().data
        
        print(f"✅ Connected to Oracle Cloud. Namespace: {namespace}")
        
        # Get all existing screenshots
        response = object_storage.list_objects(
            namespace_name=namespace,
            bucket_name='screenshot-bucket',
            prefix='screenshots/',
            fields='name,timeCreated'
        )
        
        existing_screenshots = []
        for obj in response.data.objects:
            if obj.name.lower().endswith('.png'):
                existing_screenshots.append(obj.name)
        
        print(f"📸 Found {len(existing_screenshots)} existing screenshots in bucket")
        
        if existing_screenshots:
            print("\n📋 Existing screenshots that will be marked as processed:")
            for screenshot in existing_screenshots:
                print(f"   • {screenshot}")
        
        # Create state file marking all as processed
        state_data = {
            'processed_files': existing_screenshots,
            'last_updated': datetime.now().isoformat(),
            'reset_time': datetime.now().isoformat(),
            'note': 'State reset - all existing screenshots marked as processed'
        }
        
        state_file = Path('/tmp/processed_screenshots.json')
        with open(state_file, 'w') as f:
            json.dump(state_data, f, indent=2)
        
        print(f"\n✅ State reset complete!")
        print(f"📄 State file: {state_file}")
        print(f"🎯 The watcher will now ONLY process screenshots captured AFTER this reset")
        print()
        print("🚀 Next steps:")
        print("1. Start the screenshot watcher: python3 screenshot_watcher.py")
        print("2. Take a new screenshot on your Mac")
        print("3. Watch the watcher process only the NEW screenshot")
        
    except Exception as e:
        print(f"❌ Error resetting state: {e}")

if __name__ == "__main__":
    reset_watcher_state()
