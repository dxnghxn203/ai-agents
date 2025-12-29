from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import AsyncGenerator
import asyncio
import json
import uuid
import os
from app.models.schemas import LottieGenRequest, LottieResumeRequest, SSEEvent
# from app.agents.motion_gen.graph import get_app
# from app.services.sse import SSEManager
# from app.services.events import event_emitter
# Temporarily disabled due to missing dependencies

router = APIRouter(prefix="/v1/lottie", tags=["lottie"])


@router.post("/gen")
async def generate_lottie_animation(request: LottieGenRequest):
    """Generate Lottie JSON animation from template"""

    try:
        # Create conversation ID if not provided
        conversation_id = request.conversation_id or f"json_{uuid.uuid4().hex[:8]}"

        # Load template from app/templates/lottie_samples
        template_path = f"app/templates/lottie_samples/{request.lottie_template_id}.json"

        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail=f"Template not found: {request.lottie_template_id}")

        # Read template JSON
        with open(template_path, "r", encoding="utf-8") as f:
            template_json = json.load(f)

        # Apply prompt-based modifications to the template
        modified_json = apply_prompt_modifications(template_json, request.prompt)

        # Save generated JSON
        output_path = f"app/output/{conversation_id}_animation.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(modified_json, f, indent=2, ensure_ascii=False)

        return {
            "conversation_id": conversation_id,
            "status": "completed",
            "json_path": output_path,
            "json_filename": os.path.basename(output_path),
            "download_url": f"/v1/lottie/json/{conversation_id}/download",
            "preview_url": f"/v1/lottie/json/{conversation_id}/preview"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


def apply_prompt_modifications(template_json: dict, prompt: str) -> dict:
    """Apply prompt-based modifications to the template JSON"""
    import re

    # Create a modified copy
    result = template_json.copy()

    # Simple text replacement based on prompt
    # This is a basic implementation - you can enhance it with AI-based text generation
    prompt_lower = prompt.lower()

    # Replace placeholder texts based on prompt keywords
    layers = result.get("layers", [])

    for layer in layers:
        if layer.get("ty") == 5:  # Text layer
            text_data = layer.get("t", {}).get("d", "")

            # Simple keyword-based replacements
            if "công ty" in prompt_lower or "company" in prompt_lower:
                if "logo" in prompt_lower or "thương hiệu" in prompt_lower:
                    text_data = "Company Logo"
                else:
                    text_data = "Company Name"

            elif "sản phẩm" in prompt_lower or "product" in prompt_lower:
                text_data = "Product Name"

            elif "dịch vụ" in prompt_lower or "service" in prompt_lower:
                text_data = "Service Name"

            elif "liên hệ" in prompt_lower or "contact" in prompt_lower:
                text_data = "Contact Info"

            # Apply the modified text
            layer["t"]["d"] = text_data

    return result


@router.get("/video/{conversation_id}/download")
async def download_video(conversation_id: str):
    """Download video file"""

    try:
        video_path = f"app/output/videos/{conversation_id}_output.mp4"

        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        # Return video file
        from fastapi.responses import FileResponse
        return FileResponse(
            path=video_path,
            media_type='video/mp4',
            filename=f"{conversation_id}_animation.mp4"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/")
async def root():
    """Simple root endpoint"""
    return {
        "message": "Lovinbot Video Generation API",
        "status": "running",
        "endpoints": {
            "generate": "/v1/lottie/gen",
            "download": "/v1/lottie/video/{conversation_id}/download"
        }
    }