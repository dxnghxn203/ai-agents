import logging
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List
import asyncio
import traceback

from src.models.schemas import AppState
from src.utils.file_handler import save_upload_files, cleanup_files

from src.agents.analyzer import AnalyzerAgent
from src.agents.script import ScriptAgent

# Celery tasks for Phase 5
from src.tasks.audio_task import generate_audio
from src.tasks.visual_task import generate_images
from src.tasks.camera_task import create_animations
from src.tasks.merge_task import merge_video

logger = logging.getLogger(__name__)

router = APIRouter()

# Queue đơn giản để stream progress theo channel_id (in-memory, đủ cho dev)
progress_queues: dict[str, asyncio.Queue] = {}

async def progress_generator(channel_id: str):
    # Get the existing queue that was created in the endpoint
    queue = progress_queues.get(channel_id)

    if not queue:
        yield "data: Error: No progress queue found\n\n"
        return

    logger.info(f"📡 [API] Progress generator started for channel {channel_id}")

    try:
        yield "data: Kết nối streaming thành công. Bắt đầu xử lý...\n\n"

        while True:
            logger.debug(f"📡 [API] Waiting for message on queue {channel_id}")
            message = await queue.get()

            logger.debug(f"📡 [API] Got message: {message}")

            if isinstance(message, dict):
                # Handle structured messages with events
                if "event" in message and message["event"] != "message":
                    yield f"event: {message['event']}\n"
                yield f"data: {message['data']}\n\n"
                logger.info(f"📡 [API] Emitted structured event: {message.get('event', 'progress')}")
            else:
                # Handle simple string messages
                yield message
                logger.debug(f"📡 [API] Emitted simple message")

            queue.task_done()

            # Kiểm tra điều kiện kết thúc
            if isinstance(message, dict) and message.get("event") in ["complete", "error"]:
                logger.info(f"📡 [API] Progress generator ending due to event: {message.get('event')}")
                break

    except asyncio.CancelledError:
        logger.info(f"📡 [API] Progress generator cancelled for channel {channel_id}")
        pass
    except Exception as e:
        logger.error(f"❌ [API] Progress generator error: {e}")
        yield f"event: error\ndata: Stream error: {str(e)}\n\n"
    finally:
        progress_queues.pop(channel_id, None)
        logger.info(f"📡 [API] Progress generator cleaned up for channel {channel_id}")
        
@router.post("/generate-video")
async def generate_video(
    prompt: str = Form(..., description="Mô tả video bạn muốn tạo"),
    images: List[UploadFile] = File(default=[], description="Hình ảnh tham khảo (tùy chọn)"),
    background_tasks: BackgroundTasks = None
):
    input_image_paths = []
    state = None

    logger.info("🚀 [API] Starting video generation endpoint...")
    logger.info(f"📋 [API] Received prompt: {prompt[:100]}...")
    logger.info(f"🖼️ [API] Received {len(images)} image files")

    for i, img in enumerate(images):
        logger.info(f"📸 [API] Image {i+1}: {img.filename}, size: {img.size} bytes")

    try:
        # 1. Lưu images
        if images:
            logger.info(f"💾 [API] Saving {len(images)} uploaded images...")
            input_image_paths = await save_upload_files(images)
            logger.info(f"✅ [API] Images saved to: {input_image_paths}")

        # 2. Tạo state
        logger.info(f"🔧 [API] Creating AppState...")
        state = AppState(prompt=prompt, input_image_paths=input_image_paths)
        logger.info(f"🆔 [API] Created channel_id: {state.channel_id}")

        state.add_progress(f"📥 Đã nhận prompt: {prompt[:60]}...")
        if input_image_paths:
            state.add_progress(f"🖼️ Đã nhận {len(input_image_paths)} hình ảnh")

        # 3. TẠO QUEUE NGAY TẠI ĐÂY TRƯỚC KHI XỬ LÝ (QUAN TRỌNG!)
        logger.info(f"📡 [API] Creating progress queue for channel {state.channel_id}...")
        queue = asyncio.Queue()
        progress_queues[state.channel_id] = queue
        logger.info(f"✅ [API] Progress queue created")

        # Emit khởi đầu
        await queue.put({"event": "progress", "data": "🚀 Khởi động hệ thống..."})
        await queue.put({"event": "progress", "data": f"Đã nhận {len(input_image_paths)} ảnh tham khảo"})

        # 4. Helper emit progress
        async def emit_progress(message: str):
            logger.info(f"📡 [API] Progress: {message}")
            await queue.put({"event": "progress", "data": message})

        # 5. CHẠY ANALYZER AGENT
        logger.info(f"🔍 [API] Initializing and running Analyzer Agent...")
        await emit_progress("🔍 Bắt đầu Analyzer Agent...")

        analyzer = AnalyzerAgent()
        logger.info(f"✅ [API] AnalyzerAgent initialized")

        state = await analyzer.run(state, progress_callback=emit_progress)
        logger.info(f"✅ [API] AnalyzerAgent completed")

        await emit_progress("✅ Analyzer Agent hoàn thành!")
        logger.info(f"📡 [API] Emitting analysis_result event")
        await queue.put({"event": "analysis_result", "data": state.analysis_result or {}})

        # 6. CHẠY SCRIPT AGENT
        logger.info(f"📝 [API] Initializing and running Script Agent...")
        await emit_progress("📝 Bắt đầu Script Agent...")

        script_agent = ScriptAgent()
        logger.info(f"✅ [API] ScriptAgent initialized")

        state = await script_agent.run(state, progress_callback=emit_progress)
        logger.info(f"✅ [API] ScriptAgent completed")

        await emit_progress("✅ Script Agent hoàn thành!")
        logger.info(f"📡 [API] Emitting script event")
        await queue.put({"event": "script", "data": state.script or {}})

        # Skip Phase 5 & 6 (Audio, Visual, Camera agents and Video Merge)
        # Only stream planner and script results as requested
        logger.info(f"📋 [API] Skipping audio/camera/visual agents - returning planner and script results only")
        await emit_progress("📋 Hoàn thành giai đoạn lập kế hoạch và kịch bản")
        await emit_progress("⏭️ Bỏ qua các tác vụ audio, camera, visual theo yêu cầu")

        # Add results to state for reference
        state.tasks = {
            "analyzer": {"status": "completed", "result": state.analysis_result},
            "script": {"status": "completed", "result": state.script},
            "audio": {"status": "skipped", "message": "Bỏ qua theo yêu cầu"},
            "visual": {"status": "skipped", "message": "Bỏ qua theo yêu cầu"},
            "camera": {"status": "skipped", "message": "Bỏ qua theo yêu cầu"},
            "merge": {"status": "skipped", "message": "Bỏ qua theo yêu cầu"}
        }

        logger.info(f"🎉 [API] Planner and Script phases completed successfully!")
        await emit_progress("🎉 Đã hoàn thành Planner và Script!")

        # Send completion event
        await queue.put({"event": "complete", "data": "Hoàn thành giai đoạn lập kế hoạch và kịch bản!"})
        await queue.put({"event": "final_results", "data": {
            "analysis_result": state.analysis_result,
            "script": state.script,
            "message": "Chỉ hoàn thành planner và script, bỏ qua các tác vụ media theo yêu cầu"
        }})

    except Exception as e:
        error_msg = f"❌ Lỗi: {str(e)}"
        logger.error(f"❌ [API] {error_msg}")
        logger.error(f"❌ [API] Error type: {type(e).__name__}")
        logger.error(f"❌ [API] Full traceback: {traceback.format_exc()}")

        if state and state.channel_id in progress_queues:
            logger.info(f"📡 [API] Emitting error to queue")
            await progress_queues[state.channel_id].put({"event": "error", "data": error_msg})

        if state:
            state.add_progress(error_msg)

        # Re-raise để FastAPI xử lý HTTP response
        raise

    finally:
        logger.info(f"🧹 [API] Starting cleanup...")
        if input_image_paths:
            logger.info(f"🗑️ [API] Scheduling cleanup for {len(input_image_paths)} files")
            background_tasks.add_task(cleanup_files, input_image_paths)

        logger.info(f"📊 [API] Final state summary:")
        if state:
            logger.info(f"   - Channel ID: {state.channel_id}")
            logger.info(f"   - Progress events: {len(state.progress_events)}")
            logger.info(f"   - Analysis result: {'✅' if state.analysis_result else '❌'}")
            logger.info(f"   - Script: {'✅' if state.script else '❌'}")

    # Trả về stream (queue đã sẵn sàng)
    logger.info(f"📡 [API] Returning StreamingResponse for channel {state.channel_id}")
    return StreamingResponse(
        progress_generator(state.channel_id),
        media_type="text/event-stream"
    )