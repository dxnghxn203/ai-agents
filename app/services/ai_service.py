"""
AI Service for prompt analysis and text generation.
"""

import json
import logging
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """
    AI Service for analyzing user prompts and generating appropriate text replacements.
    """

    def __init__(self):
        """Initialize AI service with configuration."""
        self.api_key = settings.openrouter_api_key
        self.model = "anthropic/claude-3.5-sonnet"
        self.base_url = "https://openrouter.ai/api/v1"

    async def analyze_prompt(self, prompt: str, template_type: str) -> Dict[str, Any]:
        """
        Analyze user prompt to determine text replacements for Lottie template.

        Args:
            prompt: User's input prompt
            template_type: Type of Lottie template being used

        Returns:
            Dictionary containing analysis results with text replacements
        """
        try:
            # Create prompt for AI analysis
            analysis_prompt = self._create_analysis_prompt(prompt, template_type)

            # Call OpenAI API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": """Bạn là một chuyên gia phân tích text cho animation Lottie.
Hãy phân tích prompt người dùng và đề xuất text replacement phù hợp.
Trả về JSON với cấu trúc:
{
    "replacements": [
        {
            "layer_id": "id_of_layer",
            "original_text": "text gốc",
            "new_text": "text mới",
            "reason": "lý do thay thế"
        }
    ],
    "image_instructions": {
        "use_uploaded_image": true/false,
        "image_placement": "description of where to place image"
    }
}"""
                            },
                            {
                                "role": "user",
                                "content": analysis_prompt
                            }
                        ],
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"}
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    return json.loads(content)
                else:
                    logger.error(f"AI API Error: {response.status_code} - {response.text}")
                    return self._get_fallback_replacements(prompt)

        except Exception as e:
            logger.error(f"Error analyzing prompt: {str(e)}")
            return self._get_fallback_replacements(prompt)

    def _create_analysis_prompt(self, prompt: str, template_type: str) -> str:
        """
        Create prompt for AI analysis based on template type.

        Args:
            prompt: User's input prompt
            template_type: Type of Lottie template

        Returns:
            Formatted prompt for AI analysis
        """
        template_descriptions = {
            "Glowing Fish Loader": "Template có con cá bơi, có thể chứa text ở thân cá",
            "Confetti": "Template có hiệu ứng confetti, có thể chứa text liên quan celebration"
        }

        return f"""
Phân tích prompt này cho template loại: {template_type}
Mô template: {template_descriptions.get(template_type, "Chưa mô tả")}

Prompt người dùng: "{prompt}"

Hãy phân tích và đề xuất text replacement phù hợp.
"""

    def _get_fallback_replacements(self, prompt: str) -> Dict[str, Any]:
        """
        Get fallback replacements when AI service is unavailable.

        Args:
            prompt: User's input prompt

        Returns:
            Fallback replacement dictionary
        """
        prompt_lower = prompt.lower()
        replacements = []

        # Simple keyword-based fallback
        if any(keyword in prompt_lower for keyword in ["công ty", "company"]):
            replacements.append({
                "layer_id": "text_1",
                "original_text": "Sample Text",
                "new_text": "Company Name",
                "reason": "User mentioned company"
            })

        if any(keyword in prompt_lower for keyword in ["sản phẩm", "product"]):
            replacements.append({
                "layer_id": "text_1",
                "original_text": "Sample Text",
                "new_text": "Product Name",
                "reason": "User mentioned product"
            })

        if any(keyword in prompt_lower for keyword in ["dịch vụ", "service"]):
            replacements.append({
                "layer_id": "text_1",
                "original_text": "Sample Text",
                "new_text": "Service Name",
                "reason": "User mentioned service"
            })

        return {
            "replacements": replacements,
            "image_instructions": {
                "use_uploaded_image": False,
                "image_placement": None
            }
        }