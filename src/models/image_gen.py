"""Image Generation Management."""

from typing import Dict, Any, Optional, List
import logging
from .manager import ModelManager, ModelType, ModelProvider

logger = logging.getLogger(__name__)


class ImageGenConfig:
    """Configuration for image generation models."""

    def __init__(self, config_data: Dict[str, Any]):
        self.provider = config_data.get("provider")
        self.model_id = config_data.get("model_id")
        self.name = config_data.get("name")
        self.parameters = config_data.get("parameters", {})
        self.cost_per_generation = config_data.get("cost_per_generation", 0)
        self.capabilities = config_data.get("capabilities", [])
        self.styles = config_data.get("styles", [])

    def get_replicate_config(self) -> Dict[str, Any]:
        """Get Replicate-specific configuration."""
        return {
            "input": self.parameters
        }

    def get_openai_config(self) -> Dict[str, Any]:
        """Get OpenAI DALL-E specific configuration."""
        return {
            "model": self.model_id,
            "size": f"{self.parameters.get('width', 1024)}x{self.parameters.get('height', 1024)}",
            "quality": self.parameters.get("quality", "standard"),
            "n": self.parameters.get("num_outputs", 1)
        }

class ImageGenManager:
    """Manager for image generation models."""

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager()
        self._client_cache: Dict[str, Any] = {}

    def get_primary_config(self, provider: Optional[ModelProvider] = None) -> Optional[ImageGenConfig]:
        """Get primary image generation configuration."""
        model_name = self.model_manager.get_primary_model(ModelType.IMAGE_GENERATION, provider)
        if not model_name:
            return None

        config_data = self.model_manager.get_config(model_name)
        return ImageGenConfig(config_data) if config_data else None

    def get_fallback_chain(self) -> List[ImageGenConfig]:
        """Get ordered fallback chain for image generation."""
        model_names = self.model_manager.get_fallback_chain(ModelType.IMAGE_GENERATION)
        configs = []

        for model_name in model_names:
            config_data = self.model_manager.get_config(model_name)
            if config_data:
                configs.append(ImageGenConfig(config_data))

        return configs

    def get_client(self, config: ImageGenConfig):
        """Get initialized client for a configuration."""
        cache_key = f"{config.provider}_{config.model_id}"

        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        client = None

        if config.provider == ModelProvider.REPLICATE.value:
            try:
                import replicate
                client = replicate
            except ImportError:
                logger.error("Replicate library not installed")
        elif config.provider == ModelProvider.OPENAI.value:
            try:
                import openai
                client = openai.OpenAI()
            except ImportError:
                logger.error("OpenAI library not installed")

        if client:
            self._client_cache[cache_key] = client

        return client

    async def generate_image(
        self,
        prompt: str,
        output_path: str,
        config: Optional[ImageGenConfig] = None,
        style: Optional[str] = None,
        negative_prompt: Optional[str] = None
    ) -> bool:
        """Generate image from text prompt."""
        configs = self.get_fallback_chain()

        if config:
            configs.insert(0, config)

        for img_config in configs:
            try:
                client = self.get_client(img_config)
                if not client:
                    continue

                # Prepare parameters
                params = img_config.parameters.copy()
                params["prompt"] = prompt

                if negative_prompt:
                    params["negative_prompt"] = negative_prompt

                if style and style in img_config.styles:
                    params["style"] = style

                if img_config.provider == ModelProvider.REPLICATE.value:
                    output = client.run(
                        img_config.model_id,
                        input=params
                    )

                    # Replicate returns a URL, download the image
                    if isinstance(output, list) and output:
                        import requests
                        response = requests.get(output[0])
                        response.raise_for_status()

                        with open(output_path, "wb") as f:
                            f.write(response.content)
                        return True

                elif img_config.provider == ModelProvider.OPENAI.value:
                    response = client.images.generate(
                        **img_config.get_openai_config()
                    )

                    if response.data:
                        image_url = response.data[0].url
                        import requests
                        response = requests.get(image_url)
                        response.raise_for_status()

                        with open(output_path, "wb") as f:
                            f.write(response.content)
                        return True

            except Exception as e:
                logger.warning(f"Failed to generate image with {img_config.name}: {e}")
                continue

        logger.error("All image generation providers failed")
        return False
