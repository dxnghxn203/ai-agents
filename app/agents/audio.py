"""Audio Agent for generating voice narration from script."""

import os
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
import uuid

from .base import StreamingAgent
from ..models.tts import TTSManager
from ..core.config import settings

logger = logging.getLogger(__name__)


class AudioAgent(StreamingAgent):
    """Agent for generating audio narration from script."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.output_dir = Path(self.config.get("output_dir", "generated_audio"))
        self.audio_format = self.config.get("audio_format", "mp3")
        self.voice_id = self.config.get("voice_id", "default")
        self.model_id = self.config.get("model_id", "eleven_multilingual_v2")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize TTS manager
        self.tts_manager = TTSManager()

    def validate_input(self, **kwargs) -> bool:
        """Validate input parameters."""
        narration = kwargs.get("narration")
        if not narration or not isinstance(narration, str):
            logger.error("Invalid narration input")
            return False

        storyboard = kwargs.get("storyboard", [])
        if not isinstance(storyboard, list):
            logger.error("Invalid storyboard input")
            return False

        return True

    def get_output_schema(self) -> Dict[str, Any]:
        """Get the expected output schema."""
        return {
            "agent_id": str,
            "agent_type": str,
            "audio_files": List[Dict[str, Any]],
            "full_narration_audio": str,
            "total_audio_duration": float,
            "segments_generated": int,
            "successful_generations": int,
            "failed_generations": int,
            "execution_time": float,
            "output_dir": str
        }

    async def generate_audio_for_segment(
        self,
        text: str,
        segment_id: str,
        scene_id: int
    ) -> Optional[Dict[str, Any]]:
        """Generate audio for a single narration segment."""
        try:
            await self.report_progress(
                (scene_id / 10) * 100,  # Assuming 10 segments max
                f"🎙️ Generating audio for Scene {scene_id} narration..."
            )

            # Generate unique filename
            filename = f"narration_{segment_id}_{uuid.uuid4().hex[:8]}.{self.audio_format}"
            output_path = self.output_dir / filename

            logger.info(f"🎙️ [AudioAgent] Generating audio for segment {segment_id}: {text[:50]}...")

            # Generate audio using TTSManager
            success = await self.tts_manager.generate_speech(
                text=text,
                output_path=str(output_path),
                voice=self.voice_id
            )

            if success and output_path.exists():
                logger.info(f"✅ [AudioAgent] Successfully generated audio for segment {segment_id}")
                return {
                    "segment_id": segment_id,
                    "scene_id": scene_id,
                    "audio_path": str(output_path),
                    "filename": filename,
                    "text": text,
                    "duration_seconds": 0,  # Will be calculated later
                    "generation_time": 0
                }
            else:
                logger.error(f"❌ [AudioAgent] Failed to generate audio for segment {segment_id}")
                return None

        except Exception as e:
            logger.error(f"❌ [AudioAgent] Error generating audio for segment {segment_id}: {e}")
            return None

    async def generate_full_narration_audio(
        self,
        full_text: str
    ) -> Optional[str]:
        """Generate audio for the complete narration."""
        try:
            await self.report_progress(90, "🎙️ Generating complete narration audio...")

            filename = f"full_narration_{uuid.uuid4().hex[:8]}.{self.audio_format}"
            output_path = self.output_dir / filename

            logger.info(f"🎙️ [AudioAgent] Generating full narration audio: {full_text[:100]}...")

            success = await self.tts_manager.generate_speech(
                text=full_text,
                output_path=str(output_path),
                voice=self.voice_id
            )

            if success and output_path.exists():
                logger.info(f"✅ [AudioAgent] Successfully generated full narration audio")
                return str(output_path)
            else:
                logger.error(f"❌ [AudioAgent] Failed to generate full narration audio")
                return None

        except Exception as e:
            logger.error(f"❌ [AudioAgent] Error generating full narration audio: {e}")
            return None

    def get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file."""
        try:
            # You would typically use a library like pydub or librosa here
            # For now, return an estimate based on text length
            # Estimate: 150 words per minute = 2.5 words per second
            text = Path(audio_path).stem.replace("narration_", "").split("_")[0]
            return len(text.split()) / 2.5 if text else 5.0
        except Exception:
            return 5.0  # Default duration

    async def execute_with_streaming(self, **kwargs) -> Dict[str, Any]:
        """Execute audio generation with streaming updates."""
        narration = kwargs.get("narration", "")
        storyboard = kwargs.get("storyboard", [])

        await self.report_progress(0, "🎙️ Starting audio generation...")

        logger.info(f"🎙️ [AudioAgent] Processing narration with {len(storyboard)} scenes")

        # Generate audio for each scene's narration segment
        generated_audio = []
        successful_count = 0
        failed_count = 0

        for i, scene in enumerate(storyboard):
            scene_id = scene.get("scene_id", i + 1)
            narration_segment = scene.get("narration_segment", "")

            if narration_segment:
                segment_id = f"scene_{scene_id}"
                audio_result = await self.generate_audio_for_segment(
                    narration_segment,
                    segment_id,
                    scene_id
                )

                if audio_result:
                    # Calculate duration
                    audio_result["duration_seconds"] = self.get_audio_duration(audio_result["audio_path"])
                    generated_audio.append(audio_result)
                    successful_count += 1
                else:
                    failed_count += 1

        # Generate full narration audio
        full_narration_path = await self.generate_full_narration_audio(narration)

        # Calculate total duration
        total_duration = sum(audio.get("duration_seconds", 0) for audio in generated_audio)

        await self.report_progress(
            100,
            f"✅ Audio generation complete! {successful_count} segments + full narration generated"
        )

        return {
            "audio_files": generated_audio,
            "full_narration_audio": full_narration_path,
            "total_audio_duration": total_duration,
            "segments_generated": len(storyboard),
            "successful_generations": successful_count,
            "failed_generations": failed_count,
            "output_dir": str(self.output_dir),
            "voice_used": self.voice_id,
            "model_used": self.model_id
        }

    def get_cost_estimate(self, **kwargs) -> float:
        """Get estimated cost for audio generation."""
        narration = kwargs.get("narration", "")
        storyboard = kwargs.get("storyboard", [])

        # Estimate cost: $0.30 per 1000 characters for ElevenLabs
        total_characters = len(narration) + sum(
            len(scene.get("narration_segment", "")) for scene in storyboard
        )
        cost_per_1k_chars = 0.30
        return (total_characters / 1000) * cost_per_1k_chars