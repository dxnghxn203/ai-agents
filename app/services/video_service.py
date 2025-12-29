"""
Video service for converting Lottie JSON to video format.
"""

import json
import os
import subprocess
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import uuid
from app.core.config import settings

logger = logging.getLogger(__name__)


class VideoService:
    """
    Service for converting Lottie animations to video format.
    """

    def __init__(self):
        """Initialize video service."""
        self.output_dir = Path(settings.output_dir)
        self.ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """
        Check if FFmpeg is available on the system.

        Returns:
            True if FFmpeg is available, False otherwise
        """
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    async def convert_lottie_to_video(
        self,
        lottie_json: Dict[str, Any],
        output_filename: Optional[str] = None,
        duration: float = 5.0,
        resolution: str = "1280x720"
    ) -> str:
        """
        Convert Lottie JSON to video format using FFmpeg.

        Args:
            lottie_json: Lottie animation data
            output_filename: Custom output filename
            duration: Video duration in seconds
            resolution: Video resolution as "widthxheight"

        Returns:
            Path to the generated video file

        Raises:
            RuntimeError: If FFmpeg is not available or conversion fails
        """
        if not self.ffmpeg_available:
            raise RuntimeError("FFmpeg is not installed or not available")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename if not provided
        if not output_filename:
            output_filename = f"lottie_video_{uuid.uuid4().hex[:8]}.mp4"

        # Create temporary JSON file
        json_path = self.output_dir / f"temp_{uuid.uuid4().hex[:8]}.json"
        video_path = self.output_dir / output_filename

        try:
            # Write Lottie JSON to temporary file
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(lottie_json, f, indent=2, ensure_ascii=False)

            # Convert Lottie to video using FFmpeg
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-f", "lavfi",
                "-i", f"testsrc2=duration={duration}:size={resolution}:rate=30",
                "-i", str(json_path),
                "-filter_complex",
                f"[0:v]format=yuva420p,colorchannelmixer=aa=0.2[base];"
                f"[1:v]lottie=format=json:filename={json_path}[lottie];"
                f"[base][lottie]overlay",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(video_path)
            ]

            # Run FFmpeg command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                raise RuntimeError(f"Video conversion failed: {result.stderr}")

            logger.info(f"Video created successfully: {video_path}")
            return str(video_path)

        except Exception as e:
            logger.error(f"Error converting Lottie to video: {str(e)}")
            raise RuntimeError(f"Video conversion failed: {str(e)}")

        finally:
            # Clean up temporary JSON file
            if json_path.exists():
                json_path.unlink()

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Get metadata information about a video file.

        Args:
            video_path: Path to the video file

        Returns:
            Dictionary containing video metadata
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"FFprobe error: {result.stderr}")
                return {}

        except Exception as e:
            logger.error(f"Error getting video info: {str(e)}")
            return {}

    async def generate_preview_gif(
        self,
        video_path: str,
        duration: float = 3.0
    ) -> str:
        """
        Generate a GIF preview from the video.

        Args:
            video_path: Path to the source video
            duration: Duration of the GIF in seconds

        Returns:
            Path to the generated GIF file
        """
        try:
            gif_path = video_path.replace(".mp4", ".gif")

            cmd = [
                "ffmpeg",
                "-y",
                "-t", str(duration),
                "-i", video_path,
                "-filter_complex", "[0:v] fps=10,scale=640:-1:flags=lanczos",
                "-f", "gif",
                gif_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error(f"GIF generation error: {result.stderr}")
                raise RuntimeError(f"GIF generation failed: {result.stderr}")

            return gif_path

        except Exception as e:
            logger.error(f"Error generating GIF: {str(e)}")
            raise