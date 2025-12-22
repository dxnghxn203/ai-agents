"""Video merge task using MoviePy to combine audio, images, and animations."""
import logging
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

from celery import Celery

from celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, name='src.tasks.merge_task.merge_video')
def merge_video(self, channel_id: str, storyboard: List[Dict[str, Any]], audio_result: Dict[str, Any],
               visual_result: Dict[str, Any], camera_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge audio, images, and animations into final video using MoviePy.

    Args:
        channel_id: Unique channel identifier for progress tracking
        storyboard: Storyboard with scene information
        audio_result: Audio generation results
        visual_result: Image generation results
        camera_result: Animation generation results

    Returns:
        Dictionary containing final video information
    """
    logger.info(f"🎬 [MergeTask] Starting video merge for channel {channel_id}")
    logger.info(f"🎭 [MergeTask] Merging {len(storyboard)} scenes into final video")

    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Initializing video merger...', 'channel_id': channel_id}
        )

        # Create output directory
        temp_dir = Path("tmp") / channel_id
        output_dir = temp_dir / "final"
        output_dir.mkdir(parents=True, exist_ok=True)

        final_video_path = output_dir / f"final_video_{channel_id}.mp4"

        logger.info(f"📁 [MergeTask] Output directory: {output_dir}")

        # Prepare scene data
        scene_data = _prepare_scene_data(storyboard, audio_result, visual_result, camera_result)

        self.update_state(
            state='PROGRESS',
            meta={'status': 'Creating video clips for each scene...', 'channel_id': channel_id}
        )

        # Create video clips for each scene
        scene_clips = []
        for i, scene in enumerate(scene_data):
            self.update_state(
                state='PROGRESS',
                meta={
                    'status': f'Creating scene {i+1}/{len(scene_data)}',
                    'channel_id': channel_id,
                    'scene_id': scene.get('scene_id', i+1)
                }
            )

            try:
                clip_path = _create_scene_clip(scene, temp_dir)
                if clip_path:
                    scene_clips.append(clip_path)
                    logger.info(f"✅ [MergeTask] Scene {scene.get('scene_id', i+1)} clip created: {clip_path}")
                else:
                    logger.warning(f"⚠️ [MergeTask] Scene {scene.get('scene_id', i+1)} clip creation failed")
                    # Create fallback clip
                    fallback_path = _create_fallback_scene_clip(scene, temp_dir)
                    if fallback_path:
                        scene_clips.append(fallback_path)

            except Exception as clip_error:
                logger.error(f"❌ [MergeTask] Error creating scene {scene.get('scene_id', i+1)}: {clip_error}")
                # Continue with other scenes
                continue

        self.update_state(
            state='PROGRESS',
            meta={'status': 'Merging scenes into final video...', 'channel_id': channel_id}
        )

        # Merge all scene clips into final video
        if scene_clips:
            logger.info(f"🎬 [MergeTask] Merging {len(scene_clips)} scene clips...")
            final_path = _merge_scene_clips(scene_clips, final_video_path, audio_result)

            if final_path and Path(final_path).exists():
                # Get video duration and file size
                import cv2
                cap = cv2.VideoCapture(final_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                duration = frame_count / fps if fps > 0 else 0
                cap.release()

                file_size = Path(final_path).stat().st_size

                result = {
                    "channel_id": channel_id,
                    "status": "completed",
                    "final_video_path": final_path,
                    "final_video_filename": Path(final_path).name,
                    "duration_seconds": duration,
                    "file_size_bytes": file_size,
                    "total_scenes": len(scene_clips),
                    "output_dir": str(output_dir),
                    "service": "moviepy"
                }

                logger.info(f"🎉 [MergeTask] Video merge completed for channel {channel_id}")
                logger.info(f"📊 [MergeTask] Final video: {final_path}")
                logger.info(f"📊 [MergeTask] Duration: {duration:.2f}s, Size: {file_size:,} bytes")

                return result
            else:
                raise Exception("Failed to create final merged video")
        else:
            raise Exception("No scene clips were created")

    except Exception as e:
        error_msg = f"Video merge failed: {str(e)}"
        logger.error(f"❌ [MergeTask] {error_msg}")

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
            "final_video_path": None
        }


def _prepare_scene_data(storyboard: List[Dict[str, Any]], audio_result: Dict[str, Any],
                        visual_result: Dict[str, Any], camera_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare combined scene data from all sources."""
    scene_data = []

    # Create lookup dictionaries
    audio_files = {audio.get('scene_id', 'complete'): audio for audio in audio_result.get('audio_files', [])}
    generated_images = {img.get('scene_id'): img for img in visual_result.get('generated_images', [])}
    animations = {anim.get('scene_id'): anim for anim in camera_result.get('animation_files', [])}

    for scene in storyboard:
        scene_id = scene.get('scene_id', 1)

        scene_info = {
            "scene_id": scene_id,
            "description": scene.get('description', ''),
            "duration_seconds": scene.get('duration_seconds', 5),
            "narration_segment": scene.get('narration_segment', ''),
            "transition": scene.get('transition', 'none'),
            "audio_file": audio_files.get('complete') or audio_files.get(scene_id),
            "image_file": generated_images.get(scene_id),
            "animation_file": animations.get(scene_id)
        }

        scene_data.append(scene_info)

    return scene_data


def _create_scene_clip(scene: Dict[str, Any], temp_dir: Path) -> Optional[str]:
    """Create a video clip for a single scene."""
    try:
        from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, CompositeVideoClip, ColorClip
        from moviepy.video.fx import resize, fadein, fadeout

        scene_id = scene["scene_id"]
        duration = scene["duration_seconds"]
        transition = scene["transition"]

        # Create output path for this scene
        scene_output = temp_dir / f"scene_{scene_id:03d}.mp4"

        logger.info(f"🎬 [MergeTask] Creating scene {scene_id} clip (duration: {duration}s)")

        # Create base visual clip
        visual_clip = None

        # Try to use image file
        image_file = scene.get("image_file")
        if image_file and image_file.get("image_path") and Path(image_file["image_path"]).exists():
            logger.info(f"🖼️ [MergeTask] Using image: {image_file['image_path']}")
            visual_clip = ImageClip(image_file["image_path"])
            visual_clip = visual_clip.set_duration(duration)
        else:
            # Create fallback visual
            logger.info(f"🎨 [MergeTask] Creating fallback visual for scene {scene_id}")
            visual_clip = _create_fallback_visual(scene, duration)

        if not visual_clip:
            raise Exception("Failed to create visual clip")

        # Resize to standard dimensions
        visual_clip = visual_clip.resize((1024, 1024))

        # Apply transition effects
        if transition == "fade_in":
            visual_clip = visual_clip.fadein(1)
        elif transition == "fade_out":
            visual_clip = visual_clip.fadeout(1)

        # Add audio if available
        audio_clip = None
        audio_file = scene.get("audio_file")
        if audio_file and audio_file.get("path") and Path(audio_file["path"]).exists():
            logger.info(f"🎵 [MergeTask] Using audio: {audio_file['path']}")
            try:
                audio_clip = AudioFileClip(audio_file["path"])
                # Adjust audio duration to match video
                if audio_clip.duration > duration:
                    audio_clip = audio_clip.subclip(0, duration)
                elif audio_clip.duration < duration:
                    # Loop audio if needed
                    remaining_duration = duration - audio_clip.duration
                    if remaining_duration > 0:
                        # Create looped version
                        looped_audio = audio_clip
                        while looped_audio.duration < duration:
                            looped_audio = looped_audio.concatenate(audio_clip)
                        audio_clip = looped_audio.subclip(0, duration)

                visual_clip = visual_clip.set_audio(audio_clip)
            except Exception as audio_error:
                logger.warning(f"⚠️ [MergeTask] Audio processing failed: {audio_error}")

        # Write the scene clip
        visual_clip.write_videofile(
            str(scene_output),
            fps=24,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=str(scene_output).replace('.mp4', '_temp.m4a'),
            remove_temp=True
        )

        return str(scene_output)

    except Exception as e:
        logger.error(f"❌ [MergeTask] Error creating scene clip: {e}")
        return None


def _create_fallback_visual(scene: Dict[str, Any], duration: float) -> Optional['VideoClip']:
    """Create a fallback visual clip when image generation fails."""
    try:
        from moviepy.editor import ColorClip, TextClip
        import numpy as np

        # Create colored background based on scene mood
        scene_id = scene["scene_id"]
        description = scene["description"][:50] if scene.get("description") else f"Scene {scene_id}"

        # Create background
        bg = ColorClip(size=(1024, 1024), color=(100, 150, 200), duration=duration)

        # Add text overlay
        try:
            txt = TextClip(
                f"Scene {scene_id}\n{description}",
                fontsize=60,
                color='white',
                font='Arial'
            ).set_position('center').set_duration(duration)

            return CompositeVideoClip([bg, txt])
        except:
            # Return just the background if text fails
            return bg

    except Exception as e:
        logger.error(f"❌ [MergeTask] Fallback visual failed: {e}")
        return None


def _create_fallback_scene_clip(scene: Dict[str, Any], temp_dir: Path) -> Optional[str]:
    """Create a simple fallback scene clip."""
    try:
        from moviepy.editor import VideoClip
        import numpy as np

        scene_id = scene["scene_id"]
        duration = scene["duration_seconds"]
        scene_output = temp_dir / f"fallback_scene_{scene_id:03d}.mp4"

        def make_frame(t):
            w, h = 1024, 1024

            # Create simple animated background
            progress = t / duration
            color_intensity = int(128 + 127 * np.sin(progress * 2 * np.pi))

            frame = np.full((h, w, 3), [color_intensity, 150, 200], dtype=np.uint8)

            # Add scene number
            center_y, center_x = h // 2, w // 2
            cv2.circle(frame, (center_x, center_y), 200, (255, 255, 255), -1)

            return frame

        clip = VideoClip(make_frame, duration=duration)
        clip.write_videofile(str(scene_output), fps=12, codec='libx264')

        return str(scene_output)

    except Exception as e:
        logger.error(f"❌ [MergeTask] Fallback scene clip failed: {e}")
        return None


def _merge_scene_clips(scene_clips: List[str], final_output: Path, audio_result: Dict[str, Any]) -> str:
    """Merge all scene clips into final video."""
    try:
        from moviepy.editor import VideoFileClip, concatenate_videoclips

        logger.info(f"🎬 [MergeTask] Loading {len(scene_clips)} scene clips...")

        # Load all scene clips
        clips = []
        for clip_path in scene_clips:
            if Path(clip_path).exists():
                clip = VideoFileClip(clip_path)
                clips.append(clip)
                logger.info(f"📹 [MergeTask] Loaded clip: {clip_path} (duration: {clip.duration}s)")
            else:
                logger.warning(f"⚠️ [MergeTask] Clip not found: {clip_path}")

        if not clips:
            raise Exception("No valid scene clips to merge")

        # Concatenate all clips
        logger.info(f"🔗 [MergeTask] Concatenating {len(clips)} clips...")
        final_clip = concatenate_videoclips(clips, method="compose")

        # Add background audio if available and no scene-specific audio was used
        if not any(clip.audio for clip in clips):
            audio_files = audio_result.get('audio_files', [])
            if audio_files:
                main_audio = audio_files[0].get('path')
                if main_audio and Path(main_audio).exists():
                    try:
                        from moviepy.editor import AudioFileClip
                        audio = AudioFileClip(main_audio)

                        # Loop audio if needed
                        if audio.duration < final_clip.duration:
                            loops_needed = int(final_clip.duration / audio.duration) + 1
                            audio = audio.loop(loops_needed)

                        # Trim audio to match video
                        audio = audio.subclip(0, final_clip.duration)
                        final_clip = final_clip.set_audio(audio)
                        logger.info(f"🎵 [MergeTask] Added background audio: {main_audio}")
                    except Exception as audio_error:
                        logger.warning(f"⚠️ [MergeTask] Background audio failed: {audio_error}")

        # Write final video
        logger.info(f"💾 [MergeTask] Writing final video: {final_output}")
        final_clip.write_videofile(
            str(final_output),
            fps=24,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=str(final_output).replace('.mp4', '_temp.m4a'),
            remove_temp=True
        )

        # Close all clips
        for clip in clips:
            clip.close()
        final_clip.close()

        return str(final_output)

    except Exception as e:
        logger.error(f"❌ [MergeTask] Error merging clips: {e}")
        return None