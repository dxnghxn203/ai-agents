import uvicorn
from app.main import app
import os

def ensure_directories():
    """Ensure all required directories exist"""
    os.makedirs("app/previews", exist_ok=True)
    os.makedirs("app/templates/lottie_samples", exist_ok=True)
    os.makedirs("app/output", exist_ok=True)
    os.makedirs("app/output/videos", exist_ok=True)
    print(f"✅ Created directories: app/output, app/output/videos")

if __name__ == "__main__":
    # Create required directories
    ensure_directories()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,  # Hot reload trong dev,
        workers=1
    )