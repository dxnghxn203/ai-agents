"""Script Agent for generating video narration and storyboard."""
from typing import Dict, Any, Optional, Callable
import logging

from src.models.schemas import AppState
from src.services.ai.text_llm import TextLLMService

logger = logging.getLogger(__name__)


class ScriptAgent:
    """Agent responsible for generating video script with narration and storyboard."""

    def __init__(self):
        """Initialize the ScriptAgent with text LLM service."""
        self.llm_service = TextLLMService(temperature=0.3)

    async def run(
        self,
        state: AppState,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> AppState:
        """
        Run the Script Agent to generate narration and storyboard.

        Args:
            state: Current application state with analysis_result from Analyzer Agent
            progress_callback: Optional callback function for progress updates

        Returns:
            Updated state with script data containing narration and storyboard
        """
        try:
            if progress_callback:
                await progress_callback("📝 Bắt đầu Script Agent...")

            # Validate input
            if not state.prompt:
                raise ValueError("Thiếu prompt để tạo kịch bản")

            if not state.analysis_result:
                if progress_callback:
                    await progress_callback("⚠️ Không có kết quả phân tích, tạo kịch bản từ prompt gốc")
                analysis_result = None
            else:
                analysis_result = state.analysis_result
                if progress_callback:
                    await progress_callback("📋 Sử dụng kết quả phân tích để tạo kịch bản chi tiết")

            # Generate script using LLM
            if progress_callback:
                await progress_callback("🤖 Đang tạo kịch bản với AI...")

            script_data = await self.llm_service.generate_script(
                prompt=state.prompt,
                analysis_result=analysis_result
            )

            # Validate script generation
            if "error" in script_data:
                logger.error(f"Script generation error: {script_data['error']}")
                if progress_callback:
                    await progress_callback(f"⚠️ Cảnh báo: {script_data['error']}")

            # Store script in state
            state.script = script_data

            # Emit progress with script details
            storyboard_count = len(script_data.get("storyboard", []))
            total_duration = script_data.get("total_duration", 0)

            if progress_callback:
                await progress_callback(f"🎬 Đã tạo kịch bản với {storyboard_count} cảnh")
                await progress_callback(f"⏱️ Tổng thời lượng: {total_duration} giây")

                # Emit storyboard summary
                if storyboard_count > 0:
                    await progress_callback("📋 Storyboard:")
                    for scene in script_data.get("storyboard", []):
                        scene_id = scene.get("scene_id", 0)
                        duration = scene.get("duration_seconds", 0)
                        transition = scene.get("transition", "none")
                        await progress_callback(
                            f"   - Cảnh {scene_id}: {duration}s, transition: {transition}"
                        )

            # Add final progress message
            if progress_callback:
                await progress_callback("✅ Script Agent hoàn thành!")

            # Log to state progress events
            state.add_progress(f"Script Agent: Generated {storyboard_count} scenes, {total_duration}s total")

            return state

        except Exception as e:
            error_msg = f"Script Agent error: {str(e)}"
            logger.error(error_msg)

            # Store error in script
            state.script = {
                "narration": "",
                "storyboard": [],
                "total_duration": 0,
                "error": error_msg
            }

            if progress_callback:
                await progress_callback(f"❌ Lỗi Script Agent: {str(e)}")

            state.add_progress(error_msg)

            # Re-raise to let the main handler deal with it
            raise

    def validate_script_quality(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the quality and completeness of generated script.

        Args:
            script_data: Generated script data

        Returns:
            Validation result with quality metrics
        """
        validation = {
            "is_valid": True,
            "issues": [],
            "score": 0,
            "metrics": {}
        }

        # Check narration
        narration = script_data.get("narration", "")
        if not narration:
            validation["issues"].append("Thiếu lời thoại")
            validation["is_valid"] = False
        elif len(narration) < 30:
            validation["issues"].append("Lời thoại quá ngắn")
        elif len(narration) > 300:
            validation["issues"].append("Lời thoại quá dài")

        # Check storyboard
        storyboard = script_data.get("storyboard", [])
        if not storyboard:
            validation["issues"].append("Thiếu storyboard")
            validation["is_valid"] = False
        elif len(storyboard) < 3:
            validation["issues"].append("Storyboard có quá ít cảnh (< 3)")
        elif len(storyboard) > 8:
            validation["issues"].append("Storyboard có quá nhiều cảnh (> 8)")

        # Check each scene
        for i, scene in enumerate(storyboard):
            if not scene.get("description"):
                validation["issues"].append(f"Cảnh {i+1}: Thiếu mô tả")
            if not scene.get("narration_segment"):
                validation["issues"].append(f"Cảnh {i+1}: Thiếu lời thoại")
            if scene.get("duration_seconds", 0) <= 0:
                validation["issues"].append(f"Cảnh {i+1}: Thời lượng không hợp lệ")

        # Calculate quality score
        base_score = 100
        validation["score"] = max(0, base_score - len(validation["issues"]) * 10)

        # Store metrics
        validation["metrics"] = {
            "narration_length": len(narration),
            "scene_count": len(storyboard),
            "total_duration": script_data.get("total_duration", 0),
            "avg_scene_duration": sum(
                scene.get("duration_seconds", 0) for scene in storyboard
            ) / max(1, len(storyboard))
        }

        return validation