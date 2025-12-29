from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.motion_gen import router as motion_gen_router
import os

# Create FastAPI app
app = FastAPI(
    title="Lovinbot Lottie JSON Generation API",
    version="1.0.0",
    description="Simple Lottie JSON generation API"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(motion_gen_router)

# Create directories if they don't exist
os.makedirs("app/output", exist_ok=True)
os.makedirs("app/templates/lottie_samples", exist_ok=True)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Lovinbot Lottie JSON Generation API",
        "version": "1.0.0",
        "endpoints": {
            "generation": "/v1/lottie/gen",
            "download": "/v1/lottie/json/{conversation_id}/download",
            "preview": "/v1/lottie/json/{conversation_id}/preview"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Lovinbot Lottie JSON Generation"}