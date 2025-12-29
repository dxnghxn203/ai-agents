import os
import json
import copy
import logging

logger = logging.getLogger(__name__)


def analyzer_agent(state) -> dict:
    """Agent to analyze Lottie template and identify placeholders"""
    try:
        state.update_current_step("analysis")
        state.add_message("system", "Đang phân tích template Lottie...")

        # Load template
        template_path = f"app/templates/lottie_samples/{state.conversation_id.split('_')[0]}.json"

        if not os.path.exists(template_path):
            state.set_error(f"Template not found: {template_path}")
            return state.model_dump()

        with open(template_path, "r", encoding="utf-8") as f:
            state.original_lottie_json = json.load(f)

        # Analyze layers
        layers = state.original_lottie_json.get("layers", [])
        placeholders = []

        for layer in layers:
            layer_id = str(layer.get("id", ""))
            layer_type = layer.get("ty", 0)
            layer_name = layer.get("nm", f"Layer {layer_id}")

            # Identify placeholder layers
            if layer_type == 5:  # Text layer
                placeholders.append({
                    "layer_id": layer_id,
                    "name": layer_name,
                    "content_type": "text",
                    "placeholder_text": layer.get("t", {}).get("d", "Sample Text")
                })
            elif layer_type == 4:  # Shape layer
                placeholders.append({
                    "layer_id": layer_id,
                    "name": layer_name,
                    "content_type": "shape",
                    "transform_editable": ["position", "scale", "rotation"]
                })

        state.placeholders = placeholders
        state.layer_structure = [
            {
                "id": str(layer.get("id", "")),
                "name": layer.get("nm", ""),
                "type": layer.get("ty", 0)
            }
            for layer in layers
        ]

        state.add_message("assistant", f"Phát hiện {len(placeholders)} placeholder(s)")

        return state.model_dump()

    except Exception as e:
        state.set_error(f"Lỗi phân tích: {str(e)}")
        return state.model_dump()


def content_planner_agent(state) -> dict:
    """Agent to plan content mapping"""
    try:
        state.update_current_step("planning")
        state.add_message("system", "Đang lập kế hoạch nội dung...")

        # Simple mapping plan
        state.mapping_plan = {
            "text_mappings": {
                "2": "Company Name"  # Map to text layer
            },
            "image_mappings": {},
            "transform_mappings": {}
        }

        state.add_message("assistant", "Đã lập kế hoạch mapping nội dung (fallback)")

        return state.model_dump()

    except Exception as e:
        state.set_error(f"Lỗi lập kế hoạch: {str(e)}")
        return state.model_dump()


def json_mapper_agent(state) -> dict:
    """Agent to map content and generate new Lottie JSON"""
    try:
        state.update_current_step("mapping")
        state.add_message("system", "Đang tạo JSON chuyển động mới...")

        if not state.mapping_plan:
            state.set_error("Thiếu kế hoạch mapping")
            return state.model_dump()

        # Deep copy original JSON
        new_json = copy.deepcopy(state.original_lottie_json)

        # Apply text mappings
        for layer_id, text_content in state.mapping_plan.get("text_mappings", {}).items():
            for layer in new_json.get("layers", []):
                if layer.get("id") == str(layer_id):
                    if layer.get("ty") == 5:  # Text layer
                        layer["t"]["d"] = text_content

        # Apply image mappings (placeholder implementation)
        for layer_id, image_info in state.mapping_plan.get("image_mappings", {}).items():
            for layer in new_json.get("layers", []):
                if layer.get("id") == str(layer_id):
                    if layer.get("ty") == 4:  # Image layer
                        layer["refId"] = f"mapped_image_{layer_id}"

        # Apply transform mappings
        for layer_id, transform_data in state.mapping_plan.get("transform_mappings", {}).items():
            for layer in new_json.get("layers", []):
                if layer.get("id") == str(layer_id):
                    if "tm" in layer:
                        tm = layer["tm"]
                        for key, value in transform_data.items():
                            if key in tm:
                                tm[key] = value

        state.generated_lottie_json = new_json

        # Save generated JSON for preview
        preview_path = f"app/previews/{state.conversation_id}_generated.json"
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        with open(preview_path, "w", encoding="utf-8") as f:
            json.dump(new_json, f, indent=2, ensure_ascii=False)

        state.add_message("assistant", "Đã tạo JSON chuyển động mới")
        state.requires_approval = True

        return state.model_dump()

    except Exception as e:
        state.set_error(f"Lỗi tạo JSON: {str(e)}")
        return state.model_dump()


def video_generator_agent(state) -> dict:
    """Agent to generate video from Lottie JSON"""
    try:
        state.update_current_step("video")
        state.add_message("system", "Đang tạo video từ Lottie JSON...")

        if not state.generated_lottie_json:
            state.set_error("Thiếu Lottie JSON để tạo video")
            return state.model_dump()

        # Import video generator
        from app.utils.video_generator import get_video_generator

        # Get video generation parameters
        video_params = state.video_generation_params or {
            "duration": 5.0,
            "fps": 30,
            "width": 512,
            "height": 512,
            "background_color": "#000000"
        }

        # Get video generator instance
        video_gen = get_video_generator()

        # Generate video asynchronously
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create new event loop if none exists
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        video_path = loop.run_until_complete(
            video_gen.generate_video_async(
                state.generated_lottie_json,
                state.conversation_id,
                **video_params
            )
        )

        if video_path:
            state.video_path = video_path
            state.add_message("assistant", f"Đã tạo video thành công: {os.path.basename(video_path)}")
        else:
            state.set_error("Tạo video thất bại")
            return state.model_dump()

        return state.model_dump()

    except Exception as e:
        state.set_error(f"Lỗi tạo video: {str(e)}")
        return state.model_dump()


def human_approval_node(state) -> dict:
    """Human-in-the-loop approval node"""
    state.update_current_step("approval")
    state.add_message("system", "Đã tạo bản xem trước, chờ bạn chỉnh sửa...")

    if state.requires_approval and state.generated_lottie_json:
        # In production, this would trigger frontend preview
        state.add_message("assistant", {
            "event": "preview_ready",
            "data": {
                "conversation_id": state.conversation_id,
                "preview_url": f"/preview/{state.conversation_id}",
                "message": "Đã tạo bản xem trước, bạn có muốn chỉnh sửa không?"
            }
        })

    return state.model_dump()


def apply_user_edits(state) -> dict:
    """Apply user edits to the generated JSON"""
    try:
        if not state.user_edits or not state.generated_lottie_json:
            return state.model_dump()

        # Apply text edits
        text_edits = state.user_edits.get("text", {})
        for layer_id, new_text in text_edits.items():
            for layer in state.generated_lottie_json.get("layers", []):
                if layer.get("id") == str(layer_id) and layer.get("ty") == 5:
                    layer["t"]["d"] = new_text

        # Apply transform edits
        transform_edits = state.user_edits.get("transform", {})
        for layer_id, transform_data in transform_edits.items():
            for layer in state.generated_lottie_json.get("layers", []):
                if layer.get("id") == str(layer_id):
                    if "tm" in layer:
                        tm = layer["tm"]
                        for key, value in transform_data.items():
                            if key in tm:
                                tm[key] = value

        state.add_message("assistant", "Đã áp chỉnh sửa của người dùng")
        state.requires_approval = True

        return state.model_dump()

    except Exception as e:
        state.set_error(f"Lỗi áp chỉnh sửa: {str(e)}")
        return state.model_dump()