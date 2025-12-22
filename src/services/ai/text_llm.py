"""Text-only LLM wrapper service for script generation."""
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from src.core.config import settings


class TextLLMService:
    """Wrapper service for text-only LLM calls with fallback support."""

    def __init__(self, temperature: float = 0.3):
        """
        Initialize the LLM service with preferred model.

        Args:
            temperature: Sampling temperature for creativity (0.0-1.0)
        """
        self.temperature = temperature

        # Ưu tiên Claude-3.5-Sonnet nếu có key, fallback GPT-4o
        if settings.anthropic_api_key:
            self.llm = ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=temperature,
                api_key=settings.anthropic_api_key
            )
            self.model_name = "claude-3-5-sonnet"
        elif settings.openai_api_key:
            self.llm = ChatOpenAI(
                model="gpt-4o",
                temperature=temperature,
                api_key=settings.openai_api_key
            )
            self.model_name = "gpt-4o"
        else:
            raise ValueError("Cần ít nhất một trong hai API key: OPENAI_API_KEY hoặc ANTHROPIC_API_KEY")

    async def generate_script(
        self,
        prompt: str,
        analysis_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate video script with narration and storyboard.

        Args:
            prompt: Original user prompt for video generation
            analysis_result: Results from Analyzer Agent (optional)

        Returns:
            Dictionary containing script with narration and storyboard
        """
        # Build the system prompt
        system_prompt = self._build_script_prompt(prompt, analysis_result)

        message = HumanMessage(content=system_prompt)

        try:
            response = await self.llm.ainvoke([message])

            # Parse JSON response
            import json
            try:
                script_data = json.loads(response.content)
            except json.JSONDecodeError:
                # Fallback: try to extract JSON from response
                content = response.content.strip()
                if "```json" in content:
                    start = content.find("```json") + 7
                    end = content.find("```", start)
                    json_str = content[start:end].strip()
                    script_data = json.loads(json_str)
                else:
                    # If still fails, create basic structure
                    script_data = {
                        "narration": response.content.strip(),
                        "storyboard": [
                            {
                                "scene_id": 1,
                                "description": "Scene based on user prompt",
                                "duration_seconds": 10,
                                "narration_segment": response.content.strip()[:100] + "...",
                                "transition": "none"
                            }
                        ],
                        "total_duration": 10,
                        "error": "Failed to parse structured response"
                    }

            # Validate and enhance the script data
            script_data = self._validate_and_enhance_script(script_data)

            return script_data

        except Exception as e:
            # Return error structure
            return {
                "narration": f"Lỗi khi tạo kịch bản: {str(e)}",
                "storyboard": [],
                "total_duration": 0,
                "error": str(e)
            }

    def _build_script_prompt(
        self,
        prompt: str,
        analysis_result: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build comprehensive prompt for script generation."""

        base_prompt = f"""
Bạn là một chuyên gia viết kịch bản video ngắn (15-30 giây).
Người dùng muốn tạo video với mô tả: "{prompt}"

"""

        if analysis_result:
            base_prompt += f"""
Dựa trên kết quả phân tích:
- Cảnh chính: {analysis_result.get('overall_scene', 'N/A')}
- Đối tượng chính: {', '.join(analysis_result.get('key_objects', []))}
- Phong cách: {analysis_result.get('style', 'N/A')}
- Màu sắc: {analysis_result.get('colors', 'N/A')}
- Cảm xúc: {analysis_result.get('mood', 'N/A')}
- Hành động: {', '.join(analysis_result.get('actions', []))}
- Độ dài đề xuất: {analysis_result.get('suggested_duration_seconds', 20)} giây

"""

        base_prompt += """
Hãy tạo kịch bản video hấp dẫn và trả về JSON với cấu trúc sau (chỉ trả về JSON, không giải thích thêm):

{
  "narration": "Lời thoại hoàn chỉnh cho video, hấp dẫn, phù hợp với mood và nội dung, khoảng 50-100 từ",
  "storyboard": [
    {
      "scene_id": 1,
      "description": "Mô tả chi tiết cảnh quay này, bao gồm góc máy, ánh sáng, bố cục, màu sắc để tạo ra hình ảnh/video",
      "duration_seconds": 5,
      "narration_segment": "Phần lời thoại对应 với cảnh này",
      "transition": "none"
    },
    {
      "scene_id": 2,
      "description": "Mô tả chi tiết cảnh quay thứ hai",
      "duration_seconds": 5,
      "narration_segment": "Phần lời thoại tiếp theo",
      "transition": "fade"
    }
  ],
  "total_duration": 20,
  "style_notes": "Ghi chú về phong cách hình ảnh, màu sắc, cảm xúc cần duy trì"
}

Yêu cầu:
- Tạo 4-6 cảnh (storyboard scenes)
- Tổng độ dài 15-30 giây
- Mỗi cảnh có mô tả visual chi tiết để AI image/video generation dễ thực hiện
- Transition types: "none", "fade", "fade_to_black", "zoom_in", "zoom_out", "pan_left", "pan_right", "slide_up", "slide_down"
- Narration phải liền mạch và hấp dẫn
- Phù hợp với mood/phong cách đã phân tích

Chỉ trả về JSON hợp lệ.
"""
        return base_prompt

    def _validate_and_enhance_script(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enhance the generated script data."""

        # Ensure required fields exist
        if "narration" not in script_data:
            script_data["narration"] = ""

        if "storyboard" not in script_data:
            script_data["storyboard"] = []

        if "total_duration" not in script_data:
            script_data["total_duration"] = 0

        # Validate storyboard
        storyboard = script_data["storyboard"]
        if not isinstance(storyboard, list):
            script_data["storyboard"] = []
        else:
            # Ensure each scene has required fields
            for i, scene in enumerate(storyboard):
                if not isinstance(scene, dict):
                    continue

                scene.setdefault("scene_id", i + 1)
                scene.setdefault("description", "")
                scene.setdefault("duration_seconds", 5)
                scene.setdefault("narration_segment", "")
                scene.setdefault("transition", "none")

                # Validate transition
                valid_transitions = [
                    "none", "fade", "fade_to_black", "zoom_in", "zoom_out",
                    "pan_left", "pan_right", "slide_up", "slide_down"
                ]
                if scene["transition"] not in valid_transitions:
                    scene["transition"] = "none"

        # Calculate total duration if not provided or incorrect
        calculated_duration = sum(
            scene.get("duration_seconds", 0)
            for scene in script_data["storyboard"]
        )

        if script_data["total_duration"] <= 0:
            script_data["total_duration"] = calculated_duration
        elif abs(script_data["total_duration"] - calculated_duration) > 5:
            # If duration differs significantly, use calculated
            script_data["total_duration"] = calculated_duration

        # Add style notes if missing
        if "style_notes" not in script_data:
            script_data["style_notes"] = "Duy trì phong cách nhất quán trong toàn bộ video"

        return script_data