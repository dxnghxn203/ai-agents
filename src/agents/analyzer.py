"""Analyzer Agent - Analyzes prompts and extracts key information for LangGraph Multi-Agent System."""

import logging
import traceback
from typing import Dict, Any, List, Optional
import json
import re
from datetime import datetime

from .base import SequentialAgent
from ..models.text_llm import TextLLMManager
from ..models.manager import ModelType, ModelProvider

# Legacy compatibility
try:
    from src.services.ai.vision import VisionAnalyzer
    from src.models.schemas import AppState
    LEGACY_SUPPORT = True
except ImportError:
    LEGACY_SUPPORT = False

logger = logging.getLogger(__name__)


class AnalyzerAgent(SequentialAgent):
    """
    Enhanced Analyzer Agent with both LangGraph and legacy support.
    Analyzes text prompts to extract style, mood, and elements for video generation.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.prerequisites = []
        self.llm_manager = TextLLMManager()

        # Legacy support
        if LEGACY_SUPPORT:
            logger.info("🔧 Initializing AnalyzerAgent with legacy support...")
            self.vision = VisionAnalyzer()
            logger.info("✅ AnalyzerAgent initialized with legacy support")

        # LangGraph support
        logger.info("🔧 Initializing AnalyzerAgent for LangGraph...")
        logger.info("✅ AnalyzerAgent ready for LangGraph Multi-Agent System")

    def validate_input(self, **kwargs) -> bool:
        """Validate input parameters for LangGraph execution."""
        prompt = kwargs.get("prompt")
        if not prompt or not isinstance(prompt, str):
            return False
        if len(prompt.strip()) < 3:
            return False
        return True

    def get_output_schema(self) -> Dict[str, Any]:
        """Get the expected output schema for LangGraph."""
        return {
            "type": "object",
            "properties": {
                "style": {"type": "string", "description": "Video style (cinematic, anime, etc.)"},
                "mood": {"type": "string", "description": "Overall mood (happy, serious, etc.)"},
                "elements": {"type": "array", "items": {"type": "string"}, "description": "Key elements to include"},
                "duration_estimate": {"type": "integer", "description": "Estimated video duration in seconds"},
                "scene_count": {"type": "integer", "description": "Recommended number of scenes"},
                "complexity": {"type": "string", "description": "Complexity level (simple, medium, complex)"},
                "target_audience": {"type": "string", "description": "Target audience"},
                "visual_themes": {"type": "array", "items": {"type": "string"}},
                "color_palette": {"type": "array", "items": {"type": "string"}},
                "camera_movements": {"type": "array", "items": {"type": "string"}},
                "key_actions": {"type": "array", "items": {"type": "string"}},
                "language": {"type": "string", "description": "Detected language"},
                "keywords": {"type": "array", "items": {"type": "string"}, "description": "Extracted keywords"},
                "entities": {"type": "array", "items": {"type": "string"}, "description": "Named entities"}
            }
        }

    async def execute(self, prompt: str, input_images: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute analysis for LangGraph workflow.

        Args:
            prompt: Text prompt for analysis
            input_images: Optional list of image paths

        Returns:
            Dictionary containing analysis results
        """
        try:
            logger.info(f"🚀 [AnalyzerAgent] Starting LangGraph analysis for: {prompt[:50]}...")

            # Language detection
            is_vietnamese = self._detect_vietnamese(prompt)

            # Create analysis prompt
            analysis_prompt = self._create_analysis_prompt(prompt, is_vietnamese)

            # Get LLM analysis
            llm_result = await self._get_llm_analysis(analysis_prompt)

            # Parse and enhance results
            analysis = self._parse_llm_result(llm_result)

            # Add additional analysis
            analysis.update({
                "original_prompt": prompt,
                "language": "vietnamese" if is_vietnamese else "english",
                "prompt_length": len(prompt),
                "estimated_cost": self.get_cost_estimate(prompt=prompt),
                "input_image_count": len(input_images) if input_images else 0
            })

            # Extract keywords and entities
            analysis["keywords"] = self._extract_keywords(prompt, is_vietnamese)
            analysis["entities"] = self._extract_entities(prompt, is_vietnamese)

            # Determine scene complexity
            analysis["complexity"] = self._determine_complexity(prompt, analysis)

            # Process images if available
            if input_images and LEGACY_SUPPORT:
                try:
                    logger.info(f"🖼️ [AnalyzerAgent] Processing {len(input_images)} images with vision analyzer")
                    vision_result = await self.vision.analyze(prompt, input_images)

                    # Merge vision analysis with text analysis
                    analysis.update({
                        "vision_analysis": vision_result,
                        "image_analysis": {
                            "processed_images": len(input_images),
                            "visual_elements": vision_result.get("key_objects", []),
                            "scene_description": vision_result.get("overall_scene", ""),
                            "suitability_score": vision_result.get("suitability_score", 0.8)
                        }
                    })

                    # Enhance elements with vision results
                    visual_elements = vision_result.get("key_objects", [])
                    if visual_elements:
                        analysis["elements"] = list(set(analysis.get("elements", []) + visual_elements))

                except Exception as e:
                    logger.warning(f"⚠️ [AnalyzerAgent] Vision analysis failed: {e}")
                    analysis["vision_error"] = str(e)

            logger.info(f"✅ [AnalyzerAgent] LangGraph analysis completed")
            return analysis

        except Exception as e:
            logger.error(f"❌ [AnalyzerAgent] LangGraph analysis failed: {e}")
            # Fallback to basic analysis
            return self._fallback_analysis(prompt, str(e))

    async def run(self, state: 'AppState', progress_callback=None) -> 'AppState':
        """
        Legacy method for backward compatibility.
        Nhận state → phân tích → cập nhật state.analysis_result
        """
        if not LEGACY_SUPPORT:
            raise RuntimeError("Legacy support not available - missing dependencies")

        logger.info("🚀 [AnalyzerAgent] Starting Legacy Analyzer Agent execution...")
        logger.info(f"📋 [AnalyzerAgent] State channel_id: {state.channel_id}")

        if progress_callback:
            await progress_callback("Đang khởi tạo Vision LLM...")

        prompt = state.prompt
        image_paths = state.input_image_paths

        logger.info(f"📋 [AnalyzerAgent] Prompt: {prompt[:100]}...")
        logger.info(f"🖼️ [AnalyzerAgent] Image count: {len(image_paths)}")

        if progress_callback:
            await progress_callback(f"Đang phân tích {len(image_paths)} hình ảnh với Vision LLM...")

        try:
            logger.info(f"🔍 [AnalyzerAgent] Calling VisionAnalyzer...")
            analysis_result = await self.vision.analyze(prompt, image_paths)

            logger.info(f"✅ [AnalyzerAgent] Vision analysis completed")
            logger.info(f"📊 [AnalyzerAgent] Analysis keys: {list(analysis_result.keys())}")

            state.analysis_result = analysis_result
            logger.info(f"💾 [AnalyzerAgent] Analysis result stored in state")

            # Extract key info for logging
            style = analysis_result.get('style', 'N/A')
            mood = analysis_result.get('mood', 'N/A')
            scene = analysis_result.get('overall_scene', 'N/A')
            objects = analysis_result.get('key_objects', [])
            score = analysis_result.get('suitability_score', 'N/A')

            logger.info(f"🎨 [AnalyzerAgent] Analysis summary:")
            logger.info(f"   - Style: {style}")
            logger.info(f"   - Mood: {mood}")
            logger.info(f"   - Scene: {scene[:50]}...")
            logger.info(f"   - Objects: {objects}")
            logger.info(f"   - Suitability Score: {score}")

            state.add_progress("Phân tích hình ảnh và prompt hoàn thành!")
            state.add_progress(f"Phong cách: {style}")
            state.add_progress(f"Cảm xúc: {mood}")

            if progress_callback:
                await progress_callback("Analyzer Agent hoàn thành thành công!")

            logger.info(f"✅ [AnalyzerAgent] Legacy Analyzer Agent completed successfully")
            return state

        except Exception as e:
            error_msg = f"Analyzer Agent lỗi: {str(e)}"
            logger.error(f"❌ [AnalyzerAgent] {error_msg}")
            logger.error(f"❌ [AnalyzerAgent] Error type: {type(e).__name__}")
            logger.error(f"❌ [AnalyzerAgent] Full traceback: {traceback.format_exc()}")

            state.add_progress(error_msg)
            if progress_callback:
                await progress_callback(error_msg)

            raise

    def _detect_vietnamese(self, text: str) -> bool:
        """Detect if the text is in Vietnamese."""
        vietnamese_chars = set('àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ')
        vietnamese_count = sum(1 for char in text.lower() if char in vietnamese_chars)
        return vietnamese_count > len(text) * 0.1

    def _create_analysis_prompt(self, prompt: str, is_vietnamese: bool) -> str:
        """Create analysis prompt for the LLM."""
        if is_vietnamese:
            return f"""Phân tích prompt sau đây và tạo ra thông tin chi tiết để tạo video:

Prompt: "{prompt}"

Hãy phân tích và trả về JSON với các trường sau:
{{
  "style": "phong cách video (cinematic, anime, documentary, etc.)",
  "mood": "tâm trạng chính (vui vẻ, nghiêm túc, lãng mạn, etc.)",
  "elements": ["yếu tố chính cần có"],
  "duration_estimate": 30,
  "scene_count": 3,
  "target_audience": "đối tượng mục tiêu",
  "visual_themes": ["chủ đề hình ảnh"],
  "color_palette": ["bảng màu chính"],
  "camera_movements": ["chuyển động camera"],
  "key_actions": ["hành động chính"]
}}"""
        else:
            return f"""Analyze the following prompt for video generation:

Prompt: "{prompt}"

Provide a JSON response with these fields:
{{
  "style": "video style (cinematic, anime, documentary, etc.)",
  "mood": "primary mood (happy, serious, romantic, etc.)",
  "elements": ["key elements to include"],
  "duration_estimate": 30,
  "scene_count": 3,
  "target_audience": "target audience",
  "visual_themes": ["visual themes"],
  "color_palette": ["main color palette"],
  "camera_movements": ["camera movements"],
  "key_actions": ["key actions"]
}}"""

    async def _get_llm_analysis(self, analysis_prompt: str) -> str:
        """Get analysis from LLM."""
        result = await self.llm_manager.generate_text(
            prompt=analysis_prompt,
            system_prompt="You are a video content analysis expert. Analyze prompts and provide detailed JSON responses."
        )

        if not result:
            raise RuntimeError("LLM analysis failed")

        return result

    def _parse_llm_result(self, llm_result: str) -> Dict[str, Any]:
        """Parse LLM result into structured data."""
        try:
            json_match = re.search(r'\{.*\}', llm_result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {
            "style": "cinematic",
            "mood": "neutral",
            "elements": self._extract_elements_from_text(llm_result),
            "duration_estimate": 30,
            "scene_count": 3,
            "target_audience": "general",
            "visual_themes": ["default"],
            "color_palette": ["natural"],
            "camera_movements": ["static", "slow_pan"],
            "key_actions": []
        }

    def _extract_elements_from_text(self, text: str) -> List[str]:
        """Extract key elements from text using simple pattern matching."""
        elements = []
        element_patterns = [
            r'\b(person|people|character|robot|animal|object)\b',
            r'\b(car|vehicle|building|house|tree|flower|sky|cloud)\b',
            r'\b(robot|ai|technology|computer|phone)\b'
        ]

        for pattern in element_patterns:
            matches = re.findall(pattern, text.lower())
            elements.extend(matches)

        return list(set(elements))[:10]

    def _extract_keywords(self, prompt: str, is_vietnamese: bool) -> List[str]:
        """Extract keywords from prompt."""
        words = re.findall(r'\b\w+\b', prompt.lower())

        if is_vietnamese:
            stop_words = {'và', 'của', 'cho', 'một', 'trong', 'với', 'là', 'có', 'để', 'tạo', 'làm'}
        else:
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}

        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        return keywords[:20]

    def _extract_entities(self, prompt: str, is_vietnamese: bool) -> List[str]:
        """Extract named entities from prompt."""
        entities = []

        if not is_vietnamese:
            entities.extend(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', prompt))

        entities.extend(re.findall(r'\d+\s*(?:second|minute|hour|meter|foot|cm|inch)s?', prompt.lower()))

        return entities[:10]

    def _determine_complexity(self, prompt: str, analysis: Dict[str, Any]) -> str:
        """Determine video complexity based on prompt and analysis."""
        complexity_score = 0

        if len(prompt) > 100:
            complexity_score += 1
        if len(prompt) > 200:
            complexity_score += 1

        elements_count = len(analysis.get("elements", []))
        if elements_count > 5:
            complexity_score += 1
        if elements_count > 10:
            complexity_score += 1

        scene_count = analysis.get("scene_count", 3)
        if scene_count > 5:
            complexity_score += 1

        camera_movements = analysis.get("camera_movements", [])
        if len(camera_movements) > 3:
            complexity_score += 1

        if complexity_score <= 2:
            return "simple"
        elif complexity_score <= 4:
            return "medium"
        else:
            return "complex"

    def _fallback_analysis(self, prompt: str, error: str) -> Dict[str, Any]:
        """Provide fallback analysis when LLM fails."""
        return {
            "style": "cinematic",
            "mood": "neutral",
            "elements": self._extract_elements_from_text(prompt),
            "duration_estimate": min(30, max(15, len(prompt) // 5)),
            "scene_count": min(5, max(2, len(prompt) // 20)),
            "target_audience": "general",
            "visual_themes": ["default"],
            "color_palette": ["natural"],
            "camera_movements": ["static"],
            "key_actions": [],
            "original_prompt": prompt,
            "language": "unknown",
            "prompt_length": len(prompt),
            "analysis_error": error,
            "complexity": "simple",
            "keywords": self._extract_keywords(prompt, False),
            "entities": self._extract_entities(prompt, False)
        }

    def get_cost_estimate(self, **kwargs) -> float:
        """Get estimated cost for analysis."""
        prompt = kwargs.get("prompt", "")
        return len(prompt) * 0.00001