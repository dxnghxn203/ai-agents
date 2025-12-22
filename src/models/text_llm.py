"""Text LLM Management."""

from typing import Dict, Any, Optional, List
import logging
from .manager import ModelManager, ModelType, ModelProvider

logger = logging.getLogger(__name__)


class TextLLMConfig:
    """Configuration for Text LLM models."""

    def __init__(self, config_data: Dict[str, Any]):
        self.provider = config_data.get("provider")
        self.model_id = config_data.get("model_id")
        self.name = config_data.get("name")
        self.max_tokens = config_data.get("max_tokens", 4096)
        self.temperature = config_data.get("temperature", 0.7)
        self.top_p = config_data.get("top_p", 1.0)
        self.frequency_penalty = config_data.get("frequency_penalty", 0.0)
        self.presence_penalty = config_data.get("presence_penalty", 0.0)
        self.cost_per_1k_tokens = config_data.get("cost_per_1k_tokens", {})
        self.capabilities = config_data.get("capabilities", [])
        self.use_cases = config_data.get("use_cases", [])

    def get_openai_config(self) -> Dict[str, Any]:
        """Get OpenAI-specific configuration."""
        return {
            "model": self.model_id,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty
        }

    def get_anthropic_config(self) -> Dict[str, Any]:
        """Get Anthropic-specific configuration."""
        return {
            "model": self.model_id,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p
        }


class TextLLMManager:
    """Manager for Text LLM models."""

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager()
        self._client_cache: Dict[str, Any] = {}

    def get_primary_config(self, provider: Optional[ModelProvider] = None) -> Optional[TextLLMConfig]:
        """Get primary LLM configuration."""
        model_name = self.model_manager.get_primary_model(ModelType.TEXT_LLM, provider)
        if not model_name:
            return None

        config_data = self.model_manager.get_config(model_name)
        return TextLLMConfig(config_data) if config_data else None

    def get_fallback_chain(self) -> List[TextLLMConfig]:
        """Get ordered fallback chain for LLMs."""
        model_names = self.model_manager.get_fallback_chain(ModelType.TEXT_LLM)
        configs = []

        for model_name in model_names:
            config_data = self.model_manager.get_config(model_name)
            if config_data:
                configs.append(TextLLMConfig(config_data))

        return configs

    def get_client(self, config: TextLLMConfig):
        """Get initialized client for a configuration."""
        cache_key = f"{config.provider}_{config.model_id}"

        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        client = None

        if config.provider == ModelProvider.OPENAI.value:
            try:
                import openai
                client = openai.OpenAI()
            except ImportError:
                logger.error("OpenAI library not installed")
        elif config.provider == ModelProvider.ANTHROPIC.value:
            try:
                import anthropic
                client = anthropic.Anthropic()
            except ImportError:
                logger.error("Anthropic library not installed")

        if client:
            self._client_cache[cache_key] = client

        return client

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[TextLLMConfig] = None
    ) -> Optional[str]:
        """Generate text using the available LLM."""
        configs = self.get_fallback_chain()

        if config:
            configs.insert(0, config)

        for llm_config in configs:
            try:
                client = self.get_client(llm_config)
                if not client:
                    continue

                if llm_config.provider == ModelProvider.OPENAI.value:
                    response = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        **llm_config.get_openai_config()
                    )
                    return response.choices[0].message.content

                elif llm_config.provider == ModelProvider.ANTHROPIC.value:
                    if system_prompt:
                        messages = [
                            {"role": "user", "content": f"{system_prompt}\n\n{prompt}"}
                        ]
                    else:
                        messages = [
                            {"role": "user", "content": prompt}
                        ]

                    response = client.messages.create(
                        messages=messages,
                        **llm_config.get_anthropic_config()
                    )
                    return response.content[0].text if response.content else None

            except Exception as e:
                logger.warning(f"Failed to generate with {llm_config.name}: {e}")
                continue

        logger.error("All LLM providers failed")
        return None

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, config: TextLLMConfig) -> float:
        """Estimate cost for text generation."""
        cost_data = config.cost_per_1k_tokens
        prompt_cost = (prompt_tokens / 1000) * cost_data.get("prompt", 0)
        completion_cost = (completion_tokens / 1000) * cost_data.get("completion", 0)
        return prompt_cost + completion_cost

    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all available text LLM models."""
        models = []
        model_names = self.model_manager.list_models_by_type(ModelType.TEXT_LLM)

        for model_name in model_names:
            config_data = self.model_manager.get_config(model_name)
            if config_data:
                models.append({
                    "name": model_name,
                    "provider": config_data.get("provider"),
                    "model_id": config_data.get("model_id"),
                    "display_name": config_data.get("name"),
                    "is_primary": config_data.get("is_primary", False),
                    "priority": config_data.get("priority", 999)
                })

        return sorted(models, key=lambda x: x["priority"])