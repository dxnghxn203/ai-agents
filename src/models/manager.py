"""Model Configuration Manager."""

from typing import Dict, Any, Optional, List
import json
from pathlib import Path
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """Supported model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    ELEVENLABS = "elevenlabs"
    REPLICATE = "replicate"
    HUGGINGFACE = "huggingface"
    AZURE = "azure"
    LOCAL = "local"


class ModelType(Enum):
    """Model types."""
    TEXT_LLM = "text_llm"
    TTS = "tts"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    EMBEDDING = "embedding"
    TRANSLATION = "translation"


class ModelManager:
    """Centralized model configuration manager."""

    def __init__(self, config_dir: str = "src/models/configs"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._configs: Dict[str, Any] = {}
        self._load_all_configs()

    def _load_all_configs(self):
        """Load all model configurations."""
        for config_file in self.config_dir.glob("*.json"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    model_name = config_file.stem
                    self._configs[model_name] = config
                    logger.info(f"Loaded model config: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load config {config_file}: {e}")

    def get_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific model."""
        return self._configs.get(model_name)

    def list_models_by_type(self, model_type: ModelType) -> List[str]:
        """List all models of a specific type."""
        return [
            name for name, config in self._configs.items()
            if config.get("type") == model_type.value
        ]

    def list_models_by_provider(self, provider: ModelProvider) -> List[str]:
        """List all models from a specific provider."""
        return [
            name for name, config in self._configs.items()
            if config.get("provider") == provider.value
        ]

    def get_primary_model(self, model_type: ModelType, provider: Optional[ModelProvider] = None) -> Optional[str]:
        """Get the primary model for a type, optionally filtered by provider."""
        candidates = self.list_models_by_type(model_type)

        if provider:
            candidates = [name for name in candidates
                         if self._configs[name].get("provider") == provider.value]

        # Return the first model marked as primary or the first one
        for name in candidates:
            config = self._configs[name]
            if config.get("is_primary", False):
                return name

        return candidates[0] if candidates else None

    def get_fallback_chain(self, model_type: ModelType) -> List[str]:
        """Get ordered fallback chain for a model type."""
        candidates = self.list_models_by_type(model_type)

        # Sort by priority (lower number = higher priority)
        sorted_models = sorted(
            candidates,
            key=lambda name: self._configs[name].get("priority", 999)
        )

        return sorted_models

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate a model configuration."""
        required_fields = ["type", "provider", "model_id"]

        for field in required_fields:
            if field not in config:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate provider
        try:
            ModelProvider(config["provider"])
        except ValueError:
            logger.error(f"Invalid provider: {config['provider']}")
            return False

        # Validate type
        try:
            ModelType(config["type"])
        except ValueError:
            logger.error(f"Invalid model type: {config['type']}")
            return False

        return True

    def save_config(self, model_name: str, config: Dict[str, Any]) -> bool:
        """Save a model configuration."""
        if not self.validate_config(config):
            return False

        config_file = self.config_dir / f"{model_name}.json"

        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            self._configs[model_name] = config
            logger.info(f"Saved model config: {model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save config {model_name}: {e}")
            return False

    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get all model configurations."""
        return self._configs.copy()

    def reload_configs(self):
        """Reload all configurations from disk."""
        self._configs.clear()
        self._load_all_configs()
        logger.info("Reloaded all model configurations")