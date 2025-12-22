import base64
import logging
import traceback
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from src.core.config import settings

logger = logging.getLogger(__name__)

class VisionAnalyzer:
    def __init__(self):
        logger.info("🔧 Initializing VisionAnalyzer...")

        # Ưu tiên Claude nếu có key, fallback sang GPT-4o
        if settings.anthropic_api_key:
            logger.info("🤖 [VisionAnalyzer] Using Claude-3.5-Sonnet for vision analysis")
            self.llm = ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0.2,
                api_key=settings.anthropic_api_key
            )
            self.model_name = "claude-3-5-sonnet"
        elif settings.openai_api_key:
            logger.info("🤖 [VisionAnalyzer] Using GPT-4o for vision analysis")
            self.llm = ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                openai_api_key=settings.openai_api_key,
                model_name="openai/gpt-4o",
                temperature=0.2,
            )
            self.model_name = "openai/gpt-4o"
        else:
            logger.error("❌ [VisionAnalyzer] No API keys found for vision services")
            raise ValueError("Cần ít nhất một trong hai API key: OPENAI_API_KEY hoặc ANTHROPIC_API_KEY")

        logger.info(f"✅ [VisionAnalyzer] Initialized with {self.model_name}")

    def encode_image(self, image_path: str) -> str:
        """Encode image thành base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def analyze(self, prompt: str, image_paths: List[str]) -> Dict[str, Any]:
        """
        Phân tích prompt + images, trả về structured JSON
        """
        logger.info(f"🔍 [VisionAnalyzer] Starting vision analysis...")
        logger.info(f"📋 [VisionAnalyzer] Prompt: {prompt[:100]}...")
        logger.info(f"🖼️ [VisionAnalyzer] Image count: {len(image_paths)}")

        # Encode tất cả images
        logger.info(f"🖼️ [VisionAnalyzer] Encoding images...")
        base64_images = []
        for i, path in enumerate(image_paths):
            try:
                logger.info(f"📸 [VisionAnalyzer] Encoding image {i+1}/{len(image_paths)}: {path}")
                encoded = self.encode_image(path)
                base64_images.append(encoded)
                logger.info(f"✅ [VisionAnalyzer] Image {i+1} encoded successfully ({len(encoded)} chars)")
            except Exception as e:
                logger.error(f"❌ [VisionAnalyzer] Failed to encode image {i+1}: {e}")
                raise

        # Tạo content cho message
        logger.info(f"🔨 [VisionAnalyzer] Building multimodal message...")
        content = [{"type": "text", "text": self._get_analysis_prompt(prompt)}]

        for i, base64_img in enumerate(base64_images):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_img}"
                }
            })

        logger.info(f"📨 [VisionAnalyzer] Message content built with {len(content)} parts")
        message = HumanMessage(content=content)

        try:
            logger.info(f"🚀 [VisionAnalyzer] Calling LLM API ({self.model_name})...")
            logger.info(f"⏱️ [VisionAnalyzer] API call started...")

            response = await self.llm.ainvoke([message])

            logger.info(f"✅ [VisionAnalyzer] API call completed")
            logger.info(f"📥 [VisionAnalyzer] Response length: {len(response.content)} characters")
            logger.info(f"📥 [VisionAnalyzer] Response preview: {response.content[:200]}...")

            # Parse response thành dict (giả sử LLM trả về JSON string)
            logger.info(f"🔍 [VisionAnalyzer] Parsing JSON response...")
            try:
                import json
                analysis = json.loads(response.content)
                logger.info(f"✅ [VisionAnalyzer] JSON parsing successful")
                logger.info(f"📊 [VisionAnalyzer] Analysis keys: {list(analysis.keys())}")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ [VisionAnalyzer] JSON parsing failed: {e}")
                # Nếu không phải JSON, trả về text thô
                logger.info(f"📝 [VisionAnalyzer] Returning raw text as analysis")
                analysis = {"raw_description": response.content.strip()}

            logger.info(f"✅ [VisionAnalyzer] Vision analysis completed successfully")
            return analysis

        except Exception as e:
            logger.error(f"❌ [VisionAnalyzer] Vision analysis failed: {str(e)}")
            logger.error(f"❌ [VisionAnalyzer] Error type: {type(e).__name__}")
            logger.error(f"❌ [VisionAnalyzer] Full traceback: {traceback.format_exc()}")
            raise

    def _get_analysis_prompt(self, user_prompt: str) -> str:
        return f"""
Bạn là chuyên gia phân tích hình ảnh và kịch bản video.
Người dùng muốn tạo video với mô tả: "{user_prompt}"

Hãy phân tích các hình ảnh được cung cấp và trả về JSON với cấu trúc sau (chỉ trả về JSON, không giải thích thêm):

{{
  "overall_scene": "mô tả tổng quát cảnh chính",
  "key_objects": ["danh sách các đối tượng chính"],
  "main_characters": ["nhân vật chính nếu có"],
  "style": "phong cách hình ảnh (realistic, cartoon, cinematic, v.v.)",
  "colors": "màu sắc chủ đạo",
  "mood": "cảm xúc tổng thể (vui vẻ, buồn, năng động, yên bình, v.v.)",
  "actions": ["các hành động đang diễn ra"],
  "suggested_duration_seconds": số giây ước lượng cho video,
  "suitability_score": điểm từ 1-10 đánh giá mức độ phù hợp của hình ảnh với prompt,
  "recommendations": ["gợi ý cải thiện hoặc bổ sung"]
}}

Chỉ trả về JSON hợp lệ.
"""