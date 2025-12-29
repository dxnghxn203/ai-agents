"""Camera animation task using OpenCV and MoviePy for effects."""
import logging
import os
from typing import Dict, List, Any
from pathlib import Path

from celery import Celery

from celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, name='src.tasks.camera_task.create_animations')
def create_animations(self, channel_id: str, storyboard: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create camera animation effects (zoom, pan, transitions) for video scenes.

    Args:
        channel_id: Unique channel identifier for progress tracking
        storyboard: List of storyboard scenes with transitions

    Returns:
        Dictionary containing animation results
    """
    logger.info(f"🎬 [CameraTask] Starting animation creation for channel {channel_id}")
    logger.info(f"🎭 [CameraTask] Processing {len(storyboard)} storyboard scenes")

    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Initializing animation service...', 'channel_id': channel_id}
        )

        # Create output directory
        temp_dir = Path("tmp") / channel_id / "animations"
        temp_dir.mkdir(parents=True, exist_ok=True)

        animation_files = []

        # Process each scene for animations
        for i, scene in enumerate(storyboard):
            scene_id = scene.get('scene_id', i + 1)
            transition = scene.get('transition', 'none')
            duration = scene.get('duration_seconds', 5)

            if transition == 'none':
                logger.info(f"⏭️ [CameraTask] Scene {scene_id}: No transition needed")
                continue

            self.update_state(
                state='PROGRESS',
                meta={
                    'status': f'Creating animation for scene {i+1}/{len(storyboard)}',
                    'channel_id': channel_id,
                    'scene_id': scene_id,
                    'transition': transition
                }
            )

            logger.info(f"🎨 [CameraTask] Scene {scene_id}: Creating {transition} animation")

            try:
                # Create animation based on transition type
                animation_config = {
                    "scene_id": scene_id,
                    "transition": transition,
                    "duration_seconds": duration,
                    "output_path": temp_dir / f"animation_{scene_id:03d}_{transition}.mp4"
                }

                animation_path = _create_transition_animation(animation_config)

                if animation_path and Path(animation_path).exists():
                    animation_files.append({
                        "scene_id": scene_id,
                        "transition": transition,
                        "duration_seconds": duration,
                        "animation_path": animation_path
                    })

                    logger.info(f"✅ [CameraTask] Scene {scene_id} animation created: {animation_path}")
                else:
                    logger.warning(f"⚠️ [CameraTask] Scene {scene_id} animation failed, using fallback")

                    # Create fallback simple animation
                    fallback_path = _create_fallback_animation(
                        scene_id, transition, duration, temp_dir
                    )
                    if fallback_path:
                        animation_files.append({
                            "scene_id": scene_id,
                            "transition": transition,
                            "duration_seconds": duration,
                            "animation_path": fallback_path,
                            "fallback": True
                        })

            except Exception as scene_error:
                logger.error(f"❌ [CameraTask] Error creating animation for scene {scene_id}: {scene_error}")
                # Continue with other scenes
                continue

        # Prepare result
        result = {
            "channel_id": channel_id,
            "status": "completed",
            "animation_files": animation_files,
            "total_animations": len(animation_files),
            "output_dir": str(temp_dir),
            "service": "opencv_moviepy"
        }

        logger.info(f"🎉 [CameraTask] Animation creation completed for channel {channel_id}")
        logger.info(f"📊 [CameraTask] Created {len(animation_files)} animations")

        return result

    except Exception as e:
        error_msg = f"Animation creation failed: {str(e)}"
        logger.error(f"❌ [CameraTask] {error_msg}")

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
            "animation_files": []
        }


def _create_transition_animation(config: Dict[str, Any]) -> str:
    """
    Create transition animation using MoviePy.

    Args:
        config: Animation configuration

    Returns:
        Path to created animation file
    """
    try:
        from moviepy.editor import VideoClip, ImageClip, ColorClip, CompositeVideoClip
        from moviepy.video.fx import resize, fadein, fadeout
        import numpy as np

        scene_id = config["scene_id"]
        transition = config["transition"]
        duration = config["duration_seconds"]
        output_path = config["output_path"]

        logger.info(f"🎬 [CameraTask] Creating {transition} animation (duration: {duration}s)")

        if transition == "fade":
            return _create_fade_animation(config)
        elif transition == "zoom_in":
            return _create_zoom_in_animation(config)
        elif transition == "zoom_out":
            return _create_zoom_out_animation(config)
        elif transition in ["pan_left", "pan_right"]:
            return _create_pan_animation(config)
        elif transition in ["slide_up", "slide_down"]:
            return _create_slide_animation(config)
        else:
            logger.warning(f"⚠️ [CameraTask] Unsupported transition: {transition}")
            return None

    except ImportError:
        logger.warning("⚠️ [CameraTask] MoviePy not available, using fallback")
        return _create_simple_fallback_animation(config)
    except Exception as e:
        logger.error(f"❌ [CameraTask] Error creating animation: {e}")
        return None


def _create_fade_animation(config: Dict[str, Any]) -> str:
    """Create fade in/out animation."""
    try:
        from moviepy.editor import ColorClip, CompositeVideoClip

        duration = config["duration_seconds"]
        output_path = config["output_path"]

        # Create a black background
        bg = ColorClip(size=(1024, 1024), color=(0, 0, 0), duration=duration)

        # Create white fade overlay
        white_bg = ColorClip(size=(1024, 1024), color=(255, 255, 255), duration=duration/2)
        white_bg = white_bg.crossfadeout(duration/2)

        # Composite and write
        final_clip = CompositeVideoClip([bg, white_bg.set_opacity(0.3)])
        final_clip.write_videofile(
            str(output_path),
            fps=24,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=str(output_path).replace('.mp4', '_temp.m4a'),
            remove_temp=True
        )

        return str(output_path)

    except Exception as e:
        logger.error(f"❌ [CameraTask] Fade animation failed: {e}")
        return None


def _create_zoom_in_animation(config: Dict[str, Any]) -> str:
    """Create zoom in animation."""
    try:
        from moviepy.editor import ImageClip, ColorClip
        import numpy as np

        duration = config["duration_seconds"]
        output_path = config["output_path"]

        # Create a gradient circle that zooms in
        def make_frame(t):
            w, h = 1024, 1024
            progress = t / duration

            # Create coordinates
            y, x = np.ogrid[:h, :w]
            center_x, center_y = w // 2, h // 2

            # Calculate distance from center
            dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)

            # Create zoom effect
            max_dist = np.sqrt(center_x**2 + center_y**2)
            zoom_factor = 1 + (2 * progress)  # Zoom from 1x to 3x

            # Create gradient circle
            radius = (max_dist / zoom_factor) * (1 - progress * 0.5)
            mask = dist <= radius

            # Create frame with gradient
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[mask] = [100 + 155 * (1 - dist[mask]/max_dist),
                          50 + 100 * (1 - dist[mask]/max_dist),
                          200]  # Blue gradient

            return frame

        from moviepy.editor import VideoClip
        clip = VideoClip(make_frame, duration=duration)
        clip.write_videofile(
            str(output_path),
            fps=24,
            codec='libx264'
        )

        return str(output_path)

    except Exception as e:
        logger.error(f"❌ [CameraTask] Zoom in animation failed: {e}")
        return None


def _create_zoom_out_animation(config: Dict[str, Any]) -> str:
    """Create zoom out animation."""
    try:
        from moviepy.editor import ImageClip, ColorClip
        import numpy as np

        duration = config["duration_seconds"]
        output_path = config["output_path"]

        # Create a gradient circle that zooms out
        def make_frame(t):
            w, h = 1024, 1024
            progress = t / duration

            # Create coordinates
            y, x = np.ogrid[:h, :w]
            center_x, center_y = w // 2, h // 2

            # Calculate distance from center
            dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)

            # Create zoom effect
            max_dist = np.sqrt(center_x**2 + center_y**2)
            zoom_factor = 3 - (2 * progress)  # Zoom from 3x to 1x

            # Create gradient circle
            radius = (max_dist / zoom_factor) * (0.5 + progress * 0.5)
            mask = dist <= radius

            # Create frame with gradient
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[mask] = [200,
                          50 + 100 * (1 - dist[mask]/max_dist),
                          100 + 155 * (1 - dist[mask]/max_dist)]  # Red gradient

            return frame

        from moviepy.editor import VideoClip
        clip = VideoClip(make_frame, duration=duration)
        clip.write_videofile(
            str(output_path),
            fps=24,
            codec='libx264'
        )

        return str(output_path)

    except Exception as e:
        logger.error(f"❌ [CameraTask] Zoom out animation failed: {e}")
        return None


def _create_pan_animation(config: Dict[str, Any]) -> str:
    """Create pan animation (left/right)."""
    try:
        from moviepy.editor import VideoClip
        import numpy as np

        duration = config["duration_seconds"]
        transition = config["transition"]
        output_path = config["output_path"]

        # Determine pan direction
        pan_right = transition == "pan_right"

        # Create a gradient that pans
        def make_frame(t):
            w, h = 1024, 1024
            progress = t / duration

            if pan_right:
                offset = int(w * progress)
            else:
                offset = int(w * (1 - progress))

            # Create gradient
            x = np.arange(w).reshape(1, w)
            x = np.repeat(x, h, axis=0)

            # Create moving gradient
            gradient = ((x + offset) % w) / w

            # Create RGB frame
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[:, :, 0] = gradient * 255  # Red channel
            frame[:, :, 1] = (1 - gradient) * 128  # Green channel
            frame[:, :, 2] = gradient * 200  # Blue channel

            return frame

        clip = VideoClip(make_frame, duration=duration)
        clip.write_videofile(
            str(output_path),
            fps=24,
            codec='libx264'
        )

        return str(output_path)

    except Exception as e:
        logger.error(f"❌ [CameraTask] Pan animation failed: {e}")
        return None


def _create_slide_animation(config: Dict[str, Any]) -> str:
    """Create slide animation (up/down)."""
    try:
        from moviepy.editor import VideoClip
        import numpy as np

        duration = config["duration_seconds"]
        transition = config["transition"]
        output_path = config["output_path"]

        # Determine slide direction
        slide_down = transition == "slide_down"

        # Create a gradient that slides
        def make_frame(t):
            w, h = 1024, 1024
            progress = t / duration

            if slide_down:
                offset = int(h * progress)
            else:
                offset = int(h * (1 - progress))

            # Create gradient
            y = np.arange(h).reshape(h, 1)
            y = np.repeat(y, w, axis=1)

            # Create moving gradient
            gradient = ((y + offset) % h) / h

            # Create RGB frame
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[:, :, 0] = 128 + gradient * 127  # Red channel
            frame[:, :, 1] = gradient * 200  # Green channel
            frame[:, :, 2] = (1 - gradient) * 255  # Blue channel

            return frame

        clip = VideoClip(make_frame, duration=duration)
        clip.write_videofile(
            str(output_path),
            fps=24,
            codec='libx264'
        )

        return str(output_path)

    except Exception as e:
        logger.error(f"❌ [CameraTask] Slide animation failed: {e}")
        return None


def _create_fallback_animation(scene_id: int, transition: str, duration: float, temp_dir: Path) -> str:
    """Create a simple fallback animation using basic shapes."""
    try:
        import numpy as np
        from moviepy.editor import VideoClip

        output_path = temp_dir / f"fallback_animation_{scene_id:03d}_{transition}.mp4"

        def make_frame(t):
            w, h = 512, 512  # Smaller for fallback
            progress = t / duration

            # Create simple animated pattern based on transition type
            if transition == "fade":
                alpha = progress
                frame = np.full((h, w, 3), [255 * alpha, 200 * alpha, 150 * alpha], dtype=np.uint8)
            elif transition == "zoom_in":
                size = int(min(w, h) * (0.3 + 0.7 * progress))
                offset = (w - size) // 2
                frame = np.zeros((h, w, 3), dtype=np.uint8)
                frame[offset:offset+size, offset:offset+size] = [255, 200, 150]
            else:
                # Default: moving stripe
                x = int(w * progress)
                frame = np.zeros((h, w, 3), dtype=np.uint8)
                frame[:, max(0, x-50):x] = [255, 200, 150]

            return frame

        clip = VideoClip(make_frame, duration=duration)
        clip.write_videofile(
            str(output_path),
            fps=12,  # Lower fps for faster processing
            codec='libx264'
        )

        return str(output_path)

    except Exception as e:
        logger.error(f"❌ [CameraTask] Fallback animation failed: {e}")
        return None


def _create_simple_fallback_animation(config: Dict[str, Any]) -> str:
    """Create a very simple animation without MoviePy."""
    try:
        import numpy as np
        import cv2

        duration = config["duration_seconds"]
        output_path = config["output_path"]
        fps = 12
        frames = int(duration * fps)

        height, width = 512, 512

        # Create simple color transition video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        for i in range(frames):
            progress = i / frames

            # Create gradient frame
            frame = np.zeros((height, width, 3), dtype=np.uint8)

            # RGB gradient based on progress
            frame[:, :, 0] = int(255 * progress)  # Red increases
            frame[:, :, 1] = int(200 * (1 - progress))  # Green decreases
            frame[:, :, 2] = int(150)  # Blue constant

            out.write(frame)

        out.release()
        return str(output_path)

    except Exception as e:
        logger.error(f"❌ [CameraTask] Simple fallback animation failed: {e}")
        return None