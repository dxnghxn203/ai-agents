"""
Lottie animation generation API endpoints.

This module provides endpoints for generating Lottie animations from templates
with AI-powered text replacements and image integration.
"""

import base64
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.services.ai_service import AIService
from app.services.video_service import VideoService
from app.models.schemas import LottieGenRequest, LottieResumeRequest, SSEEvent

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/v1/lottie", tags=["lottie"])

# Initialize services
ai_service = AIService()
video_service = VideoService()


class GenerationResponse(BaseModel):
    """Response model for Lottie generation."""
    conversation_id: str
    status: str
    json_path: str
    json_filename: str
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    video_filename: Optional[str] = None
    download_url: str
    preview_url: str
    video_preview_url: Optional[str] = None


def validate_template_file(template_id: str) -> Path:
    """
    Validate and get template file path.

    Args:
        template_id: Identifier for the template

    Returns:
        Path to the template file

    Raises:
        HTTPException: If template file is not found
    """
    template_path = Path(settings.template_dir) / f"{template_id}.json"

    if not template_path.exists():
        logger.error(f"Template not found: {template_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Template not found: {template_id}"
        )

    return template_path


def apply_text_replacements(
    template_json: Dict[str, Any],
    replacements: list
) -> Dict[str, Any]:
    """
    Apply text replacements to the Lottie template.

    Args:
        template_json: Original Lottie JSON
        replacements: List of text replacements

    Returns:
        Modified Lottie JSON
    """
    modified_json = template_json.copy()

    # Create a mapping of layer IDs to their positions
    layer_mapping = {}
    for idx, layer in enumerate(modified_json.get("layers", [])):
        layer_id = layer.get("nm", f"layer_{idx}")
        layer_mapping[layer_id] = idx

    # Apply replacements
    for replacement in replacements:
        layer_id = replacement.get("layer_id")
        new_text = replacement.get("new_text")

        if layer_id and new_text:
            # Find layer in mapping
            if layer_id in layer_mapping:
                layer_idx = layer_mapping[layer_id]
                layer = modified_json["layers"][layer_idx]

                # Update text layer
                if layer.get("ty") == 5:  # Text layer
                    if "t" in layer and "d" in layer["t"]:
                        layer["t"]["d"] = new_text
                        logger.info(f"Updated text in layer {layer_id}: {new_text}")

    return modified_json


def integrate_image(
    template_json: Dict[str, Any],
    image_data: str,
    filename: Optional[str]
) -> Dict[str, Any]:
    """
    Integrate uploaded image into the Lottie animation.

    Args:
        template_json: Lottie JSON to modify
        image_data: Base64 encoded image data
        filename: Original filename for determining image type

    Returns:
        Modified Lottie JSON with integrated image
    """
    if not image_data:
        return template_json

    modified_json = template_json.copy()

    # Determine image format
    image_format = "png"
    if filename and "." in filename:
        extension = filename.split(".")[-1].lower()
        if extension in ["jpg", "jpeg"]:
            image_format = "jpeg"
        elif extension in ["png", "gif", "webp"]:
            image_format = extension

    # Create image asset
    asset_id = f"image_{uuid.uuid4().hex[:8]}"

    # Add to assets if not exists
    if "assets" not in modified_json:
        modified_json["assets"] = []

    # Create image asset
    image_asset = {
        "id": asset_id,
        "w": 200,  # Default width
        "h": 200,  # Default height
        "u": "",    # Relative URL
        "p": f"data:image/{image_format};base64,{image_data}",
        "e": 0      # Asset type: 0 = image, 1 = precomp
    }

    modified_json["assets"].append(image_asset)

    # Update first image layer to use the uploaded image
    for layer in modified_json.get("layers", []):
        if layer.get("ty") == 2:  # Image layer
            layer["refId"] = asset_id
            logger.info(f"Integrated image into layer: {asset_id}")
            break

    return modified_json


@router.post("/gen", response_model=GenerationResponse)
async def generate_lottie_animation(
    lottie_template_id: str = Form(...),
    prompt: str = Form(...),
    conversation_id: str = Form(None),
    file: UploadFile = File(None)
) -> GenerationResponse:
    """
    Generate Lottie JSON animation from template with AI-powered enhancements.

    Args:
        request: Generation request with template and prompt
        file: Optional uploaded image file

    Returns:
        Generation response with JSON and video paths

    Raises:
        HTTPException: If generation fails
    """
    try:
        # Generate conversation ID
        conversation_id = conversation_id or f"lottie_{uuid.uuid4().hex[:8]}"

        logger.info(f"Starting generation for conversation: {conversation_id}")

        # Validate template file
        template_path = validate_template_file(lottie_template_id)

        # Load template JSON
        with open(template_path, "r", encoding="utf-8") as f:
            template_json = json.load(f)

        logger.info(f"Loaded template: {template_path}")

        # Handle file upload
        image_data = None
        if file:
            # Validate file size
            file_size = 0
            contents = await file.read()
            file_size = len(contents)

            if file_size > settings.max_file_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size: {settings.max_file_size} bytes"
                )

            # Encode image
            image_data = base64.b64encode(contents).decode()

            # Save uploaded file
            upload_dir = Path(settings.upload_dir)
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_path = upload_dir / f"{conversation_id}_{file.filename}"
            with open(file_path, "wb") as f:
                f.write(contents)

            logger.info(f"Saved uploaded image: {file_path}")

        # Analyze prompt with AI
        ai_analysis = await ai_service.analyze_prompt(
            request.prompt,
            request.lottie_template_id
        )

        logger.info(f"AI analysis completed for prompt: {request.prompt}")

        # Apply text replacements
        replacements = ai_analysis.get("replacements", [])
        modified_json = apply_text_replacements(template_json, replacements)

        # Integrate image if provided
        if image_data:
            modified_json = integrate_image(
                modified_json,
                image_data,
                file.filename if file else None
            )

        # Save modified JSON
        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        json_path = output_dir / f"{conversation_id}_animation.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(modified_json, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved Lottie JSON: {json_path}")

        # Generate video
        video_path = None
        video_filename = None
        video_preview_url = None

        try:
            video_filename = f"{conversation_id}_animation.mp4"
            video_path = await video_service.convert_lottie_to_video(
                modified_json,
                video_filename,
                duration=5.0,
                resolution="1280x720"
            )

            # Generate preview GIF
            gif_path = await video_service.generate_preview_gif(video_path, duration=3.0)
            video_preview_url = f"/v1/lottie/video/{conversation_id}/preview.gif"

            logger.info(f"Generated video: {video_path}")

        except Exception as video_error:
            logger.warning(f"Video generation failed: {str(video_error)}")
            # Continue without video if generation fails

        # Prepare response
        response = GenerationResponse(
            conversation_id=conversation_id,
            status="completed",
            json_path=str(json_path),
            json_filename=f"{conversation_id}_animation.json",
            image_path=str(file_path) if file else None,
            video_path=video_path,
            video_filename=video_filename,
            download_url=f"/v1/lottie/json/{conversation_id}/download",
            preview_url=f"/v1/lottie/json/{conversation_id}/preview",
            video_preview_url=video_preview_url
        )

        logger.info(f"Generation completed for: {conversation_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {str(e)}"
        )


@router.get("/json/{conversation_id}/download")
async def download_json(conversation_id: str) -> FileResponse:
    """
    Download generated Lottie JSON file.

    Args:
        conversation_id: Unique identifier for the generation

    Returns:
        File response for download

    Raises:
        HTTPException: If file not found
    """
    try:
        json_path = Path(settings.output_dir) / f"{conversation_id}_animation.json"

        if not json_path.exists():
            logger.error(f"JSON file not found: {json_path}")
            raise HTTPException(
                status_code=404,
                detail="JSON file not found"
            )

        return FileResponse(
            path=json_path,
            media_type='application/json',
            filename=f"{conversation_id}_animation.json"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Download failed: {str(e)}"
        )


@router.get("/json/{conversation_id}/preview")
async def preview_json(conversation_id: str) -> Dict[str, Any]:
    """
    Preview generated Lottie JSON in browser.

    Args:
        conversation_id: Unique identifier for the generation

    Returns:
        JSON content for preview

    Raises:
        HTTPException: If file not found or read error
    """
    try:
        json_path = Path(settings.output_dir) / f"{conversation_id}_animation.json"

        if not json_path.exists():
            logger.error(f"JSON file not found: {json_path}")
            raise HTTPException(
                status_code=404,
                detail="JSON file not found"
            )

        with open(json_path, "r", encoding="utf-8") as f:
            json_content = json.load(f)

        return json_content

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON file"
        )
    except Exception as e:
        logger.error(f"Preview failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Preview failed: {str(e)}"
        )


@router.get("/video/{conversation_id}/download")
async def download_video(conversation_id: str) -> FileResponse:
    """
    Download generated video file.

    Args:
        conversation_id: Unique identifier for the generation

    Returns:
        File response for download

    Raises:
        HTTPException: If video not found
    """
    try:
        video_path = Path(settings.output_dir) / f"{conversation_id}_animation.mp4"

        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            raise HTTPException(
                status_code=404,
                detail="Video file not found"
            )

        return FileResponse(
            path=video_path,
            media_type='video/mp4',
            filename=f"{conversation_id}_animation.mp4"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video download failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Video download failed: {str(e)}"
        )


@router.get("/video/{conversation_id}/preview.gif")
async def preview_video_gif(conversation_id: str) -> FileResponse:
    """
    Preview video as GIF.

    Args:
        conversation_id: Unique identifier for the generation

    Returns:
        File response for GIF preview

    Raises:
        HTTPException: If GIF not found
    """
    try:
        gif_path = Path(settings.output_dir) / f"{conversation_id}_animation.gif"

        if not gif_path.exists():
            logger.error(f"GIF file not found: {gif_path}")
            raise HTTPException(
                status_code=404,
                detail="GIF preview not available"
            )

        return FileResponse(
            path=gif_path,
            media_type='image/gif',
            filename=f"{conversation_id}_animation.gif"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GIF preview failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"GIF preview failed: {str(e)}"
        )


@router.get("/")
async def root():
    """
    Root endpoint for Lottie generation API.

    Returns:
        API information and available endpoints
    """
    return {
        "message": "Lovinbot Lottie JSON Generation API",
        "status": "running",
        "version": "2.0.0",
        "features": [
            "AI-powered prompt analysis",
            "Text replacement in Lottie animations",
            "Image integration",
            "Video generation from Lottie JSON",
            "GIF preview generation"
        ],
        "endpoints": {
            "generate": {
                "method": "POST",
                "path": "/v1/lottie/gen",
                "description": "Generate Lottie animation with AI enhancements"
            },
            "download_json": {
                "method": "GET",
                "path": "/v1/lottie/json/{conversation_id}/download",
                "description": "Download generated JSON"
            },
            "preview_json": {
                "method": "GET",
                "path": "/v1/lottie/json/{conversation_id}/preview",
                "description": "Preview JSON in browser"
            },
            "download_video": {
                "method": "GET",
                "path": "/v1/lottie/video/{conversation_id}/download",
                "description": "Download generated video"
            },
            "preview_gif": {
                "method": "GET",
                "path": "/v1/lottie/video/{conversation_id}/preview.gif",
                "description": "Preview as GIF"
            }
        },
        "requirements": {
            "ffmpeg": "Required for video generation",
            "openai_api_key": "Required for AI features"
        }
    }