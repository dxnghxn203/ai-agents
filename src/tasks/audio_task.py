"""Audio generation task using ElevenLabs TTS."""
import logging
import os
import asyncio
from typing import Dict, List, Any
from pathlib import Path

from celery import Celery
from elevenlabs.client import ElevenLabs
from elevenlabs import save

from src.core.config import settings
from celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, name='src.tasks.audio_task.generate_audio')
def generate_audio(self, channel_id: str, narration: str, storyboard: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate audio narration using ElevenLabs TTS.

    Args:
        channel_id: Unique channel identifier for progress tracking
        narration: Complete narration text for the video
        storyboard: List of storyboard scenes with narration segments

    Returns:
        Dictionary containing audio generation results
    """
    logger.info(f"🎵 [AudioTask] Starting audio generation for channel {channel_id}")
    logger.info(f"📝 [AudioTask] Narration length: {len(narration)} characters")
    logger.info(f"🎬 [AudioTask] Storyboard scenes: {len(storyboard)}")

    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Initializing TTS service...', 'channel_id': channel_id}
        )

        # Initialize ElevenLabs client
        if not settings.elevenlabs_api_key:
            logger.warning("⚠️ [AudioTask] No ElevenLabs API key, using fallback")
            return _generate_fallback_audio(channel_id, narration, storyboard)

        client = ElevenLabs(api_key=settings.elevenlabs_api_key)

        # Use a default voice
        voice = "rachel"  # You can make this configurable
        logger.info(f"🗣️ [AudioTask] Using voice: {voice}")

        # Generate audio for narration segments
        audio_files = []
        temp_dir = Path("tmp") / channel_id / "audio"
        temp_dir.mkdir(parents=True, exist_ok=True)

        self.update_state(
            state='PROGRESS',
            meta={'status': 'Generating audio segments...', 'channel_id': channel_id}
        )

        # Option 1: Generate single audio file for complete narration
        logger.info(f"🎤 [AudioTask] Generating complete narration audio...")

        try:
            # Generate audio from complete narration
            audio = client.generate(
                text=narration,
                voice=voice,
                model="eleven_multilingual_v2"
            )

            # Save audio file
            audio_path = temp_dir / "narration_complete.mp3"
            save(audio, str(audio_path))

            audio_files.append({
                "type": "narration",
                "path": str(audio_path),
                "duration": None,  # We'll calculate this later
                "scene_id": "complete"
            })

            logger.info(f"✅ [AudioTask] Complete narration saved to {audio_path}")

        except Exception as e:
            logger.error(f"❌ [AudioTask] Error generating complete narration: {e}")

            # Fallback: Generate individual scene audio
            logger.info(f"🔄 [AudioTask] Falling back to individual scene audio generation...")

            for i, scene in enumerate(storyboard):
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'status': f'Generating audio for scene {i+1}/{len(storyboard)}',
                        'channel_id': channel_id,
                        'scene_id': scene.get('scene_id', i+1)
                    }
                )

                narration_segment = scene.get('narration_segment', '').strip()
                if not narration_segment:
                    continue

                try:
                    # Generate audio for this segment
                    audio = client.generate(
                        text=narration_segment,
                        voice=voice,
                        model="eleven_multilingual_v2"
                    )

                    # Save audio file
                    audio_path = temp_dir / f"scene_{scene.get('scene_id', i+1):03d}.mp3"
                    save(audio, str(audio_path))

                    audio_files.append({
                        "type": "scene_narration",
                        "path": str(audio_path),
                        "duration": None,
                        "scene_id": scene.get('scene_id', i+1)
                    })

                    logger.info(f"✅ [AudioTask] Scene {scene.get('scene_id', i+1)} audio saved to {audio_path}")

                except Exception as segment_error:
                    logger.error(f"❌ [AudioTask] Error generating audio for scene {scene.get('scene_id', i+1)}: {segment_error}")
                    # Continue with other scenes
                    continue

        # Calculate total duration and prepare result
        result = {
            "channel_id": channel_id,
            "status": "completed",
            "audio_files": audio_files,
            "total_files": len(audio_files),
            "output_dir": str(temp_dir),
            "service": "elevenlabs"
        }

        logger.info(f"🎉 [AudioTask] Audio generation completed for channel {channel_id}")
        logger.info(f"📊 [AudioTask] Generated {len(audio_files)} audio files")

        return result

    except Exception as e:
        error_msg = f"Audio generation failed: {str(e)}"
        logger.error(f"❌ [AudioTask] {error_msg}")

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
            "audio_files": []
        }


def _generate_fallback_audio(channel_id: str, narration: str, storyboard: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate fallback audio using OpenAI TTS or return placeholder.

    This is called when ElevenLabs is not available.
    """
    logger.info(f"🔄 [AudioTask] Using fallback audio generation")

    try:
        from openai import OpenAI

        if not settings.openai_api_key:
            logger.warning("⚠️ [AudioTask] No OpenAI API key either, creating placeholder")
            return _create_audio_placeholder(channel_id)

        client = OpenAI(api_key=settings.openai_api_key)

        temp_dir = Path("tmp") / channel_id / "audio"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Generate audio using OpenAI TTS
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",  # You can make this configurable
            input=narration
        )

        audio_path = temp_dir / "narration_fallback.mp3"
        response.stream_to_file(str(audio_path))

        logger.info(f"✅ [AudioTask] Fallback audio generated: {audio_path}")

        return {
            "channel_id": channel_id,
            "status": "completed",
            "audio_files": [{
                "type": "narration",
                "path": str(audio_path),
                "duration": None,
                "scene_id": "complete"
            }],
            "total_files": 1,
            "output_dir": str(temp_dir),
            "service": "openai_tts"
        }

    except Exception as e:
        logger.error(f"❌ [AudioTask] Fallback audio generation failed: {e}")
        return _create_audio_placeholder(channel_id)


def _create_audio_placeholder(channel_id: str) -> Dict[str, Any]:
    """
    Create a placeholder audio structure when TTS is not available.

    This allows the system to continue processing even without audio generation.
    """
    logger.info(f"⚠️ [AudioTask] Creating audio placeholder for channel {channel_id}")

    return {
        "channel_id": channel_id,
        "status": "placeholder",
        "message": "Audio generation not available - using placeholder",
        "audio_files": [{
            "type": "placeholder",
            "path": None,
            "duration": 30,  # Default 30 seconds
            "scene_id": "placeholder"
        }],
        "total_files": 0,
        "output_dir": None,
        "service": "placeholder"
    }