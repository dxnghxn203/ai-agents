"""Storyboard Agent for generating images from scene descriptions."""

import os
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
import uuid

from .base import StreamingAgent
from ..models.image_gen import ImageGenManager
from ..core.config import settings

logger = logging.getLogger(__name__)


class StoryboardAgent(StreamingAgent):
    """Agent for generating storyboard images from scene descriptions."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.output_dir = Path(self.config.get("output_dir", "generated_images"))
        self.image_format = self.config.get("image_format", "jpg")
        self.max_concurrent_generations = self.config.get("max_concurrent_generations", 3)

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize image generation manager
        self.image_gen_manager = ImageGenManager()

    def validate_input(self, **kwargs) -> bool:
        """Validate input parameters."""
        storyboard = kwargs.get("storyboard")
        if not storyboard or not isinstance(storyboard, list):
            logger.error("Invalid storyboard input")
            return False

        for scene in storyboard:
            if not isinstance(scene, dict) or "description" not in scene:
                logger.error("Invalid scene format in storyboard")
                return False

        return True

    def get_output_schema(self) -> Dict[str, Any]:
        """Get the expected output schema."""
        return {
            "agent_id": str,
            "agent_type": str,
            "storyboard_images": List[Dict[str, Any]],
            "total_generated": int,
            "successful_generations": int,
            "failed_generations": int,
            "execution_time": float,
            "output_dir": str
        }

    async def generate_image_for_scene(
        self,
        scene: Dict[str, Any],
        scene_index: int,
        style_prompt: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Generate an image for a single scene."""
        try:
            await self.report_progress(
                (scene_index / 10) * 100,  # Assuming 10 scenes max
                f"🎨 Generating image for Scene {scene.get('scene_id', scene_index + 1)}..."
            )

            scene_id = scene.get("scene_id", scene_index + 1)
            description = scene.get("description", "")

            # Build enhanced prompt for image generation
            image_prompt = self._build_image_prompt(description, style_prompt, scene)

            # Generate unique filename
            filename = f"scene_{scene_id:02d}_{uuid.uuid4().hex[:8]}.{self.image_format}"
            output_path = self.output_dir / filename

            logger.info(f"🎨 [StoryboardAgent] Generating image for Scene {scene_id}: {description[:50]}...")

            # Generate image using ImageGenManager
            success = await self.image_gen_manager.generate_image(
                prompt=image_prompt,
                output_path=str(output_path),
                style=scene.get("visual_style"),
                negative_prompt="blurry, low quality, distorted, ugly, bad anatomy"
            )

            if success and output_path.exists():
                logger.info(f"✅ [StoryboardAgent] Successfully generated image for Scene {scene_id}")
                return {
                    "scene_id": scene_id,
                    "image_path": str(output_path),
                    "filename": filename,
                    "prompt_used": image_prompt,
                    "scene_description": description,
                    "duration_seconds": scene.get("duration_seconds", 5),
                    "narration_segment": scene.get("narration_segment", ""),
                    "transition": scene.get("transition", "none"),
                    "generation_time": 0  # Will be filled later
                }
            else:
                logger.error(f"❌ [StoryboardAgent] Failed to generate image for Scene {scene_id}")
                return None

        except Exception as e:
            logger.error(f"❌ [StoryboardAgent] Error generating image for scene {scene_index}: {e}")
            return None

    def _build_image_prompt(
        self,
        scene_description: str,
        style_prompt: str,
        scene: Dict[str, Any]
    ) -> str:
        """Build enhanced prompt for image generation."""

        # Base description
        base_prompt = f"cinematic shot: {scene_description}"

        # Add style information
        if style_prompt:
            base_prompt += f", {style_prompt}"

        # Add visual style from scene if available
        if "visual_style" in scene:
            base_prompt += f", {scene['visual_style']}"

        # Add quality and camera instructions
        base_prompt += ", high quality, detailed, professional photography, cinematic lighting"

        # Add camera movement hints based on transition
        transition = scene.get("transition", "none")
        if transition in ["zoom_in", "zoom_out"]:
            base_prompt += ", dynamic composition"
        elif transition in ["pan_left", "pan_right", "slide_up", "slide_down"]:
            base_prompt += ", wide shot, landscape"

        return base_prompt

    async def execute_with_streaming(self, **kwargs) -> Dict[str, Any]:
        """Execute storyboard image generation with streaming updates."""
        storyboard = kwargs.get("storyboard", [])
        style_info = kwargs.get("style_info", {})

        await self.report_progress(0, "🎬 Starting storyboard image generation...")

        # Extract style information
        style_prompt = ""
        if isinstance(style_info, dict):
            style_elements = []
            if style_info.get("style"):
                style_elements.append(style_info["style"])
            if style_info.get("mood"):
                style_elements.append(style_info["mood"])
            if style_info.get("colors"):
                style_elements.append(style_info["colors"])
            style_prompt = ", ".join(style_elements)

        logger.info(f"🎨 [StoryboardAgent] Processing {len(storyboard)} scenes")
        logger.info(f"🎨 [StoryboardAgent] Style prompt: {style_prompt}")

        # Generate images for scenes
        generated_images = []
        successful_count = 0
        failed_count = 0

        # Process scenes concurrently (in batches)
        semaphore = asyncio.Semaphore(self.max_concurrent_generations)

        async def generate_with_semaphore(scene, index):
            async with semaphore:
                return await self.generate_image_for_scene(scene, index, style_prompt)

        # Create tasks for all scenes
        tasks = [
            generate_with_semaphore(scene, i)
            for i, scene in enumerate(storyboard)
        ]

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ [StoryboardAgent] Scene {i+1} failed with exception: {result}")
                failed_count += 1
            elif result:
                generated_images.append(result)
                successful_count += 1
            else:
                failed_count += 1

        await self.report_progress(100, f"✅ Storyboard generation complete! {successful_count}/{len(storyboard)} images generated")

        return {
            "storyboard_images": generated_images,
            "total_generated": len(storyboard),
            "successful_generations": successful_count,
            "failed_generations": failed_count,
            "output_dir": str(self.output_dir),
            "style_used": style_prompt
        }

    def get_cost_estimate(self, **kwargs) -> float:
        """Get estimated cost for storyboard generation."""
        storyboard = kwargs.get("storyboard", [])
        num_scenes = len(storyboard)

        # Estimate: $0.05 per image generation (varies by provider)
        cost_per_image = 0.05
        return num_scenes * cost_per_image