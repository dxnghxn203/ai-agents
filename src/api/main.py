import logging
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.api.routes.video_generation import router as video_router
from src.api.routes.full_video_generation import router as full_video_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('logs/app.log', mode='a')  # File output
    ]
)

# Get the root logger
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Video AI Agent System",
    description="Multi-agent system to generate video from text prompt + images",
    version="0.1.0"
)

# Include routes
app.include_router(video_router, prefix="/api/v1", tags=["Video Generation"])
app.include_router(full_video_router, prefix="/api/v1", tags=["Full Video Generation"])

@app.get("/")
async def root():
    return {"message": "Video AI Agent System is running!", "status": "healthy"}

# Create directories for generated files if they don't exist
os.makedirs("generated_videos", exist_ok=True)
os.makedirs("generated_images", exist_ok=True)
os.makedirs("generated_audio", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# Mount static directories for serving generated files
app.mount("/videos", StaticFiles(directory="generated_videos"), name="videos")
app.mount("/images", StaticFiles(directory="generated_images"), name="images")
app.mount("/audio", StaticFiles(directory="generated_audio"), name="audio")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "All systems operational"}