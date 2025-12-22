from fastapi import FastAPI
from src.api.routes.video_generation import router as video_router

app = FastAPI(
    title="Video AI Agent System",
    description="Multi-agent system to generate video from text prompt + images",
    version="0.1.0"
)

# Include routes
app.include_router(video_router, prefix="/api/v1", tags=["Video Generation"])

@app.get("/")
async def root():
    return {"message": "Video AI Agent System is running!", "status": "healthy"}