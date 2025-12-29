#!/usr/bin/env python3
"""
Start the web UI for Lottie JSON Generator
"""

import subprocess
import sys
import time
import os
import threading

def check_port(port):
    """Check if port is in use"""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            if result == 0:
                return True
            return False
    except:
        return False

def wait_for_service(url, max_attempts=30):
    """Wait for service to be ready"""
    import requests

    for i in range(max_attempts):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False

def main():
    print("🚀 Starting Lottie JSON Generator UI...")

    # Check if main API is running on port 8080
    if not check_port(8080):
        print("❌ Main API is not running on port 8080")
        print("Please start the main API first:")
        print("  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080")
        sys.exit(1)

    print("✅ Main API is running")

    # Install Flask if not available
    try:
        import flask
        print("✅ Flask is installed")
    except ImportError:
        print("⚠️ Installing Flask...")
        subprocess.run([sys.executable, "-m", "pip", "install", "flask"], check=True)
        print("✅ Flask installed successfully")

    # Install requests for UI if not available
    try:
        import requests
        print("✅ Requests is installed")
    except ImportError:
        print("⚠️ Installing requests for UI...")
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
        print("✅ Requests installed successfully")

    # Change to ui directory
    ui_dir = "ui"
    if not os.path.exists(ui_dir):
        print(f"❌ UI directory '{ui_dir}' not found")
        sys.exit(1)

    os.chdir(ui_dir)

    print("\n🎨 Starting Web UI...")
    print("📱 Web UI will open at: http://localhost:5001")

    # Start Flask app
    subprocess.run([sys.executable, "main.py"])

if __name__ == "__main__":
    main()