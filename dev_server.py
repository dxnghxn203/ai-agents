#!/usr/bin/env python3
"""
Development server with watchdog auto-reload
"""

import os
import sys
import time
import subprocess
import signal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DevServerHandler(FileSystemEventHandler):
    """Watch for file changes and reload server"""

    def __init__(self):
        self.process = None
        self.start_server()

    def start_server(self):
        """Start the development server"""
        if self.process:
            self.process.terminate()
            self.process.wait()

        print("\n🔄 Restarting server...")
        self.process = subprocess.Popen([
            sys.executable, "run_motion_gen.py"
        ])
        time.sleep(2)  # Give time for server to start

    def on_modified(self, event):
        """Handle file modification events"""
        # Only watch Python files in the app directory
        if event.src_path.endswith('.py') and 'app/' in event.src_path:
            print(f"\n📁 File changed: {event.src_path}")
            self.start_server()

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    if 'handler' in globals() and handler.process:
        handler.process.terminate()
        handler.process.wait()
    print("\n👋 Server stopped")
    sys.exit(0)

def main():
    """Main function with watchdog"""
    global handler

    print("🚀 Starting development server with auto-reload...")
    print("Press Ctrl+C to stop")

    # Start watchdog observer
    event_handler = DevServerHandler()
    observer = Observer()
    observer.schedule(event_handler, path='app/', recursive=True)
    observer.start()

    # Store handler for signal handling
    handler = event_handler

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)

    try:
        while True:
            time.sleep(1)
            # Check if process is still running
            if handler.process and handler.process.poll() is not None:
                print("\n⚠️  Server process exited, restarting...")
                handler.start_server()
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        if handler.process:
            handler.process.terminate()

if __name__ == "__main__":
    main()