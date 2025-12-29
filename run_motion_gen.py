#!/usr/bin/env python3
"""
Lovinbot Motion Generation API Server

To run the server:
    python run_motion_gen.py

Environment variables required:
    OPENROUTER_API_KEY=your_openrouter_api_key
"""

import uvicorn
import os
from app.main import app

if __name__ == "__main__":
    # Check required environment variables
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY environment variable is required")
        exit(1)

    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info"
    )