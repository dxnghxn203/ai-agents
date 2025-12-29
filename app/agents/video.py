"""Video Agent for combining storyboard images and audio into final video."""

import os
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
import uuid
import subprocess

from .base import StreamingAgent
from ..core.config import settings

logger = logging.getLogger(__name__)


class VideoAgent(StreamingAgent):
    """Agent for combining storyboard images and audio into final video."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.output_dir = Path(self.config.get("output_dir", "generated_videos"))
        self.video_format = self.config.get("video_format", "mp4")
        self.fps = self.config.get("fps", 24)
        self.resolution = self.config.get("resolution", "1920x1080")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def validate_input(self, **kwargs) -> bool:
        """Validate input parameters."""
        storyboard_images = kwargs.get("storyboard_images", [])
        audio_files = kwargs.get("audio_files", [])
        storyboard = kwargs.get("storyboard", [])

        if not storyboard_images or not isinstance(storyboard_images, list):
            logger.error("Invalid storyboard_images input")
            return False

        if not storyboard or not isinstance(storyboard, list):
            logger.error("Invalid storyboard input")
            return False

        return True

    def get_output_schema(self) -> Dict[str, Any]:
        """Get the expected output schema."""
        return {
            "agent_id": str,
            "agent_type": str,
            "final_video": Dict[str, Any],
            "total_scenes": int,
            "total_duration": float,
            "video_path": str,
            "file_size_bytes": int,
            "execution_time": float,
            "output_dir": str
        }

    async def create_scene_video(
        self,
        scene_image: Dict[str, Any],
        scene_audio: Optional[Dict[str, Any]],
        scene: Dict[str, Any],
        scene_index: int
    ) -> Optional[str]:
        """Create video for a single scene."""
        try:
            await self.report_progress(
                (scene_index / 10) * 100,
                f"🎬 Creating video for Scene {scene.get('scene_id', scene_index + 1)}..."
            )

            scene_id = scene.get("scene_id", scene_index + 1)
            duration_seconds = scene.get("duration_seconds", 5)
            transition = scene.get("transition", "none")
            image_path = scene_image.get("image_path")

            if not image_path or not Path(image_path).exists():
                logger.error(f"❌ [VideoAgent] Image not found for Scene {scene_id}")
                return None

            # Generate temporary filename
            temp_video = self.output_dir / f"temp_scene_{scene_id:02d}_{uuid.uuid4().hex[:8]}.{self.video_format}"

            # Build FFmpeg command for scene video
            cmd = self._build_ffmpeg_scene_command(
                image_path=image_path,
                audio_path=scene_audio.get("audio_path") if scene_audio else None,
                output_path=str(temp_video),
                duration=duration_seconds,
                transition=transition
            )

            logger.info(f"🎬 [VideoAgent] Creating video for Scene {scene_id} with duration {duration_seconds}s")

            # Execute FFmpeg command
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout per scene
            )

            if result.returncode == 0 and temp_video.exists():
                logger.info(f"✅ [VideoAgent] Successfully created video for Scene {scene_id}")
                return str(temp_video)
            else:
                logger.error(f"❌ [VideoAgent] FFmpeg failed for Scene {scene_id}: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"❌ [VideoAgent] Timeout creating video for scene {scene_index}")
            return None
        except Exception as e:
            logger.error(f"❌ [VideoAgent] Error creating video for scene {scene_index}: {e}")
            return None

    def _build_ffmpeg_scene_command(
        self,
        image_path: str,
        audio_path: Optional[str],
        output_path: str,
        duration: float,
        transition: str
    ) -> str:
        """Build FFmpeg command for creating scene video."""

        # Base command for creating video from image
        cmd_parts = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-loop", "1",  # Loop image
            "-i", image_path,  # Input image
            "-t", str(duration),  # Duration
            "-r", str(self.fps),  # Frame rate
            "-vf", f"scale={self.resolution}:force_original_aspect_ratio=decrease,pad={self.resolution}:(ow-iw)/2:(oh-ih)/2",  # Scale and pad
        ]

        # Add audio if available
        if audio_path and Path(audio_path).exists():
            cmd_parts.extend([
                "-i", audio_path,  # Input audio
                "-c:a", "aac",  # Audio codec
                "-shortest",  # Match duration of shortest stream
            ])

        # Add transition effects
        if transition == "fade":
            cmd_parts.extend([
                "-vf", "fade=in:0:30,fade=out:st={}:d=30".format(duration - 1)
            ])
        elif transition == "fade_to_black":
            cmd_parts.extend([
                "-vf", "fade=in:0:30,fade=out:st={}:d=30:black".format(duration - 1)
            ])
        elif transition == "zoom_in":
            cmd_parts.extend([
                "-vf", "zoompan=z='if(lt(on,1),1+0.2*on,1.2)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            ])
        elif transition == "zoom_out":
            cmd_parts.extend([
                "-vf", "zoompan=z='if(lt(on,1),1.2-0.2*on,1)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            ])

        # Video codec and output
        cmd_parts.extend([
            "-c:v", "libx264",  # Video codec
            "-pix_fmt", "yuv420p",  # Pixel format
            "-crf", "23",  # Quality
            output_path
        ])

        return " ".join(cmd_parts)

    async def merge_scene_videos(
        self,
        scene_videos: List[str],
        final_output_path: str
    ) -> bool:
        """Merge individual scene videos into final video."""
        try:
            await self.report_progress(90, "🎬 Merging scenes into final video...")

            if not scene_videos:
                logger.error("❌ [VideoAgent] No scene videos to merge")
                return False

            # Create list file for FFmpeg concat
            list_file = self.output_dir / f"concat_list_{uuid.uuid4().hex[:8]}.txt"
            with open(list_file, 'w') as f:
                for video_path in scene_videos:
                    f.write(f"file '{video_path}'\n")

            # Build FFmpeg concat command
            cmd = f"ffmpeg -y -f concat -safe 0 -i {list_file} -c copy {final_output_path}"

            logger.info(f"🎬 [VideoAgent] Merging {len(scene_videos)} scenes into final video")

            # Execute FFmpeg command
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for merging
            )

            # Clean up list file and temporary videos
            list_file.unlink(missing_ok=True)
            for video_path in scene_videos:
                Path(video_path).unlink(missing_ok=True)

            if result.returncode == 0 and Path(final_output_path).exists():
                logger.info(f"✅ [VideoAgent] Successfully merged scenes into final video")
                return True
            else:
                logger.error(f"❌ [VideoAgent] FFmpeg merge failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ [VideoAgent] Timeout merging scene videos")
            return False
        except Exception as e:
            logger.error(f"❌ [VideoAgent] Error merging scene videos: {e}")
            return False

    def get_video_file_size(self, video_path: str) -> int:
        """Get file size of video in bytes."""
        try:
            return Path(video_path).stat().st_size
        except Exception:
            return 0

    async def execute_with_streaming(self, **kwargs) -> Dict[str, Any]:
        """Execute video generation with streaming updates."""
        storyboard_images = kwargs.get("storyboard_images", [])
        audio_files = kwargs.get("audio_files", [])
        storyboard = kwargs.get("storyboard", [])

        await self.report_progress(0, "🎬 Starting video generation...")

        logger.info(f"🎬 [VideoAgent] Processing {len(storyboard)} scenes for video generation")

        # Create videos for each scene
        scene_videos = []
        successful_scenes = 0
        total_duration = 0

        for i, scene in enumerate(storyboard):
            scene_id = scene.get("scene_id", i + 1)

            # Find corresponding storyboard image
            scene_image = None
            for img in storyboard_images:
                if img.get("scene_id") == scene_id:
                    scene_image = img
                    break

            # Find corresponding audio segment
            scene_audio = None
            for audio in audio_files:
                if audio.get("scene_id") == scene_id:
                    scene_audio = audio
                    break

            if not scene_image:
                logger.warning(f"⚠️ [VideoAgent] No image found for Scene {scene_id}")
                continue

            # Create scene video
            scene_video_path = await self.create_scene_video(
                scene_image, scene_audio, scene, i
            )

            if scene_video_path:
                scene_videos.append(scene_video_path)
                successful_scenes += 1
                total_duration += scene.get("duration_seconds", 5)

        # Generate final filename
        final_filename = f"final_video_{uuid.uuid4().hex[:8]}.{self.video_format}"
        final_output_path = self.output_dir / final_filename

        # Merge all scene videos
        merge_success = await self.merge_scene_videos(scene_videos, str(final_output_path))

        if not merge_success:
            raise Exception("Failed to merge scene videos")

        file_size = self.get_video_file_size(str(final_output_path))

        await self.report_progress(
            100,
            f"✅ Video generation complete! {successful_scenes}/{len(storyboard)} scenes, {total_duration}s total"
        )

        return {
            "final_video": {
                "path": str(final_output_path),
                "filename": final_filename,
                "duration_seconds": total_duration,
                "file_size_bytes": file_size,
                "resolution": self.resolution,
                "fps": self.fps,
                "format": self.video_format
            },
            "total_scenes": successful_scenes,
            "total_duration": total_duration,
            "video_path": str(final_output_path),
            "file_size_bytes": file_size,
            "output_dir": str(self.output_dir)
        }

    def get_cost_estimate(self, **kwargs) -> float:
        """Get estimated cost for video generation."""
        # Video generation is mostly computational cost, minimal API costs
        return 0.01  # Minimal cost for processing