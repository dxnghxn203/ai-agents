"""Visual generation task using Replicate API for image generation."""
import logging
import os
from typing import Dict, List, Any
from pathlib import Path
import json

from celery import Celery
from replicate import Client

from src.core.config import settings
from celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, name='src.tasks.visual_task.generate_images')
def generate_images(self, channel_id: str, storyboard: List[Dict[str, Any]], analysis_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Generate images for video storyboard using Replicate API.

    Args:
        channel_id: Unique channel identifier for progress tracking
        storyboard: List of storyboard scenes with descriptions
        analysis_result: Analysis results from Analyzer Agent for style reference

    Returns:
        Dictionary containing image generation results
    """
    logger.info(f"🎨 [VisualTask] Starting image generation for channel {channel_id}")
    logger.info(f"🎬 [VisualTask] Processing {len(storyboard)} storyboard scenes")

    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Initializing image generation service...', 'channel_id': channel_id}
        )

        # Initialize Replicate client
        if not settings.replicate_api_token:
            logger.warning("⚠️ [VisualTask] No Replicate API token, using fallback")
            return _generate_fallback_images(channel_id, storyboard)

        client = Client(api_token=settings.replicate_api_token)
        logger.info(f"🔧 [VisualTask] Replicate client initialized")

        # Create output directory
        temp_dir = Path("tmp") / channel_id / "images"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Extract style information
        style_info = _extract_style_info(analysis_result)
        logger.info(f"🎨 [VisualTask] Style info: {style_info}")

        generated_images = []

        # Generate images for each scene
        for i, scene in enumerate(storyboard):
            scene_id = scene.get('scene_id', i + 1)
            description = scene.get('description', '')
            duration = scene.get('duration_seconds', 5)

            if not description:
                logger.warning(f"⚠️ [VisualTask] No description for scene {scene_id}, skipping")
                continue

            self.update_state(
                state='PROGRESS',
                meta={
                    'status': f'Generating image for scene {i+1}/{len(storyboard)}',
                    'channel_id': channel_id,
                    'scene_id': scene_id
                }
            )

            logger.info(f"🎨 [VisualTask] Generating image for scene {scene_id}")
            logger.info(f"📝 [VisualTask] Scene description: {description[:100]}...")

            try:
                # Generate image using Stable Diffusion
                image_url = _generate_image_with_stable_diffusion(
                    client,
                    description,
                    style_info,
                    scene_id
                )

                if image_url:
                    # Download and save image
                    image_path = temp_dir / f"scene_{scene_id:03d}.png"
                    _download_image(image_url, image_path)

                    generated_images.append({
                        "scene_id": scene_id,
                        "description": description,
                        "duration_seconds": duration,
                        "image_path": str(image_path),
                        "image_url": image_url,
                        "transition": scene.get('transition', 'none')
                    })

                    logger.info(f"✅ [VisualTask] Scene {scene_id} image saved: {image_path}")
                else:
                    logger.error(f"❌ [VisualTask] Failed to generate image for scene {scene_id}")

            except Exception as scene_error:
                logger.error(f"❌ [VisualTask] Error generating image for scene {scene_id}: {scene_error}")
                # Continue with other scenes
                continue

        # Prepare result
        result = {
            "channel_id": channel_id,
            "status": "completed",
            "generated_images": generated_images,
            "total_images": len(generated_images),
            "output_dir": str(temp_dir),
            "service": "replicate_stable_diffusion"
        }

        logger.info(f"🎉 [VisualTask] Image generation completed for channel {channel_id}")
        logger.info(f"📊 [VisualTask] Generated {len(generated_images)} images")

        return result

    except Exception as e:
        error_msg = f"Image generation failed: {str(e)}"
        logger.error(f"❌ [VisualTask] {error_msg}")

        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'channel_id': channel_id
            }
        )

        return {
            "channel_id": channel_id,
            "status": "failed",
            "error": error_msg,
            "generated_images": []
        }


def _generate_image_with_stable_diffusion(client, description: str, style_info: Dict[str, str], scene_id: int) -> str:
    """
    Generate image using Stable Diffusion via Replicate.

    Args:
        client: Replicate client
        description: Scene description
        style_info: Style information from analysis
        scene_id: Scene number for logging

    Returns:
        Image URL or None if failed
    """
    try:
        # Build enhanced prompt
        enhanced_prompt = _build_image_prompt(description, style_info)
        logger.info(f"🎨 [VisualTask] Enhanced prompt for scene {scene_id}: {enhanced_prompt[:200]}...")

        # Use Stable Diffusion XL
        output = client.run(
            "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff7682a21affe81863cbe77e4",
            input={
                "prompt": enhanced_prompt,
                "negative_prompt": "blurry, low quality, distorted, text, watermark, signature, ugly, deformed",
                "width": 1024,
                "height": 1024,
                "num_outputs": 1,
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "scheduler": "DPMSolverMultistep"
            }
        )

        # Extract image URL from output
        if output and len(output) > 0:
            return output[0]
        else:
            logger.error(f"❌ [VisualTask] No output from Stable Diffusion for scene {scene_id}")
            return None

    except Exception as e:
        logger.error(f"❌ [VisualTask] Stable Diffusion failed for scene {scene_id}: {e}")
        return None


def _build_image_prompt(description: str, style_info: Dict[str, str]) -> str:
    """
    Build enhanced image prompt with style information.

    Args:
        description: Scene description
        style_info: Style information from analysis

    Returns:
        Enhanced prompt for image generation
    """
    # Base style based on analysis
    style = style_info.get('style', 'cinematic, high quality')
    mood = style_info.get('mood', 'dramatic')
    colors = style_info.get('colors', 'vibrant')

    # Build enhanced prompt
    prompt_parts = [
        description,
        f"Style: {style}, {mood} mood",
        f"Colors: {colors}",
        "High quality, detailed, sharp focus",
        "Professional photography or cinematic quality",
        "No text, no watermark, no signature",
        "8k resolution, ultra detailed"
    ]

    return ", ".join(prompt_parts)


def _extract_style_info(analysis_result: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract style information from analysis results.

    Args:
        analysis_result: Analysis results from Analyzer Agent

    Returns:
        Dictionary with style information
    """
    if not analysis_result:
        return {
            "style": "cinematic, professional",
            "mood": "engaging",
            "colors": "vibrant, natural"
        }

    # Handle both structured and raw analysis results
    if "raw_description" in analysis_result:
        # Parse from raw text (this is a simplified parser)
        raw_text = analysis_result["raw_description"]

        style_info = {
            "style": "cinematic, high quality",
            "mood": "dramatic",
            "colors": "vibrant"
        }

        # Try to extract JSON from raw text if present
        if "```json" in raw_text:
            try:
                import json
                start = raw_text.find("```json") + 7
                end = raw_text.find("```", start)
                json_str = raw_text[start:end].strip()
                parsed = json.loads(json_str)

                style_info = {
                    "style": parsed.get('style', 'cinematic'),
                    "mood": parsed.get('mood', 'dramatic'),
                    "colors": parsed.get('colors', 'vibrant')
                }
            except:
                pass  # Keep default style info

        return style_info
    else:
        # Use structured analysis result
        return {
            "style": analysis_result.get('style', 'cinematic, professional'),
            "mood": analysis_result.get('mood', 'engaging'),
            "colors": analysis_result.get('colors', 'vibrant, natural')
        }


def _download_image(url: str, output_path: Path) -> bool:
    """
    Download image from URL and save to file.

    Args:
        url: Image URL
        output_path: Output file path

    Returns:
        True if successful, False otherwise
    """
    try:
        import requests
        import time

        logger.info(f"⬇️ [VisualTask] Downloading image from {url}")

        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Verify file was created and has content
        if output_path.exists() and output_path.stat().st_size > 0:
            logger.info(f"✅ [VisualTask] Image downloaded successfully: {output_path}")
            return True
        else:
            logger.error(f"❌ [VisualTask] Downloaded file is empty or missing: {output_path}")
            return False

    except Exception as e:
        logger.error(f"❌ [VisualTask] Failed to download image: {e}")
        return False


def _generate_fallback_images(channel_id: str, storyboard: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate fallback image placeholders when image generation is not available.

    Args:
        channel_id: Channel identifier
        storyboard: Storyboard scenes

    Returns:
        Dictionary with placeholder image structure
    """
    logger.info(f"⚠️ [VisualTask] Creating image placeholders for channel {channel_id}")

    placeholder_images = []

    for i, scene in enumerate(storyboard):
        scene_id = scene.get('scene_id', i + 1)
        description = scene.get('description', '')
        duration = scene.get('duration_seconds', 5)

        placeholder_images.append({
            "scene_id": scene_id,
            "description": description,
            "duration_seconds": duration,
            "image_path": None,
            "image_url": None,
            "transition": scene.get('transition', 'none'),
            "placeholder": True,
            "message": "Image generation not available"
        })

    return {
        "channel_id": channel_id,
        "status": "placeholder",
        "message": "Image generation not available - using placeholders",
        "generated_images": placeholder_images,
        "total_images": 0,
        "output_dir": None,
        "service": "placeholder"
    }