from fastapi import FastAPI

app = FastAPI(
    title="Video AI Agent System",
    description="Multi-agent system to generate video from text prompt + images",
    version="0.1.0"
)

@app.get("/")
async def root():
    return {"message": "Video AI Agent System is running!", "status": "healthy"}