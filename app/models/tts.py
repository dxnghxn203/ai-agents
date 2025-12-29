"""TTS (Text-to-Speech) Management."""

from typing import Dict, Any, Optional, List
import logging
from .manager import ModelManager, ModelType, ModelProvider

logger = logging.getLogger(__name__)


class TTSConfig:
    """Configuration for TTS models."""

    def __init__(self, config_data: Dict[str, Any]):
        self.provider = config_data.get("provider")
        self.model_id = config_data.get("model_id")
        self.name = config_data.get("name")
        self.voice_id = config_data.get("voice_id", "alloy")
        self.voice_settings = config_data.get("voice_settings", {})
        self.voice_options = config_data.get("voice_options", [])
        self.output_format = config_data.get("output_format", "mp3")
        self.sample_rate = config_data.get("sample_rate", 24000)
        self.speed = config_data.get("speed", 1.0)
        self.languages = config_data.get("languages", ["en"])
        self.cost_per_1k_characters = config_data.get("cost_per_1k_characters", 0)
        self.capabilities = config_data.get("capabilities", [])

    def get_elevenlabs_config(self) -> Dict[str, Any]:
        """Get ElevenLabs-specific configuration."""
        return {
            "voice_id": self.voice_id,
            "model_id": self.model_id,
            "output_format": self.output_format
        }

    def get_openai_config(self) -> Dict[str, Any]:
        """Get OpenAI-specific configuration."""
        return {
            "model": self.model_id,
            "voice": self.voice_id,
            "speed": self.speed,
            "response_format": self.output_format
        }


class TTSManager:
    """Manager for TTS models."""

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager()
        self._client_cache: Dict[str, Any] = {}

    def get_primary_config(self, provider: Optional[ModelProvider] = None) -> Optional[TTSConfig]:
        """Get primary TTS configuration."""
        model_name = self.model_manager.get_primary_model(ModelType.TTS, provider)
        if not model_name:
            return None

        config_data = self.model_manager.get_config(model_name)
        return TTSConfig(config_data) if config_data else None

    def get_fallback_chain(self) -> List[TTSConfig]:
        """Get ordered fallback chain for TTS."""
        model_names = self.model_manager.get_fallback_chain(ModelType.TTS)
        configs = []

        for model_name in model_names:
            config_data = self.model_manager.get_config(model_name)
            if config_data:
                configs.append(TTSConfig(config_data))

        return configs

    def get_client(self, config: TTSConfig):
        """Get initialized client for a configuration."""
        cache_key = f"{config.provider}_{config.model_id}"

        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        client = None

        if config.provider == ModelProvider.ELEVENLABS.value:
            try:
                import elevenlabs
                client = elevenlabs.ElevenLabs()
            except ImportError:
                logger.error("ElevenLabs library not installed")
        elif config.provider == ModelProvider.OPENAI.value:
            try:
                import openai
                client = openai.OpenAI()
            except ImportError:
                logger.error("OpenAI library not installed")

        if client:
            self._client_cache[cache_key] = client

        return client

    async def generate_speech(
        self,
        text: str,
        output_path: str,
        config: Optional[TTSConfig] = None,
        voice: Optional[str] = None
    ) -> bool:
        """Generate speech from text."""
        configs = self.get_fallback_chain()

        if config:
            configs.insert(0, config)

        for tts_config in configs:
            try:
                client = self.get_client(tts_config)
                if not client:
                    continue

                # Override voice if specified
                selected_voice = voice or tts_config.voice_id

                if tts_config.provider == ModelProvider.ELEVENLABS.value:
                    import elevenlabs

                    audio = elevenlabs.generate(
                        text=text,
                        voice=selected_voice,
                        model=tts_config.model_id
                    )
                    elevenlabs.save(audio, output_path)
                    return True

                elif tts_config.provider == ModelProvider.OPENAI.value:
                    response = client.audio.speech.create(
                        input=text,
                        **tts_config.get_openai_config()
                    )

                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    return True

            except Exception as e:
                logger.warning(f"Failed to generate speech with {tts_config.name}: {e}")
                continue

        logger.error("All TTS providers failed")
        return False

    def estimate_cost(self, character_count: int, config: TTSConfig) -> float:
        """Estimate cost for TTS generation."""
        return (character_count / 1000) * config.cost_per_1k_characters

    def list_available_voices(self, config: TTSConfig) -> List[Dict[str, Any]]:
        """List available voices for a TTS configuration."""
        voices = []

        if config.provider == ModelProvider.ELEVENLABS.value:
            try:
                import elevenlabs
                client = self.get_client(config)
                if client:
                    voice_list = elevenlabs.voices()
                    for voice in voice_list:
                        voices.append({
                            "voice_id": voice.voice_id,
                            "name": voice.name,
                            "language": voice.language,
                            "gender": voice.gender
                        })
            except Exception as e:
                logger.error(f"Failed to get ElevenLabs voices: {e}")

        elif config.provider == ModelProvider.OPENAI.value:
            # OpenAI predefined voices
            for voice in config.voice_options:
                voices.append({
                    "voice_id": voice,
                    "name": voice.title(),
                    "language": "en",
                    "gender": "unknown"
                })

        return voices

    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all available TTS models."""
        models = []
        model_names = self.model_manager.list_models_by_type(ModelType.TTS)

        for model_name in model_names:
            config_data = self.model_manager.get_config(model_name)
            if config_data:
                models.append({
                    "name": model_name,
                    "provider": config_data.get("provider"),
                    "model_id": config_data.get("model_id"),
                    "display_name": config_data.get("name"),
                    "is_primary": config_data.get("is_primary", False),
                    "priority": config_data.get("priority", 999),
                    "languages": config_data.get("languages", [])
                })

        return sorted(models, key=lambda x: x["priority"])