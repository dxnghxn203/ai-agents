import logging
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
import asyncio
import traceback
import json

from src.models.schemas import AppState
from src.utils.file_handler import save_upload_files, cleanup_files

from src.agents.analyzer import AnalyzerAgent
from src.agents.script import ScriptAgent
from src.agents.storyboard import StoryboardAgent
from src.agents.audio import AudioAgent
from src.agents.video import VideoAgent

logger = logging.getLogger(__name__)

router = APIRouter()

# Queue đơn giản để stream progress theo channel_id (in-memory, đủ cho dev)
progress_queues: dict[str, asyncio.Queue] = {}

async def progress_generator(channel_id: str):
    queue = progress_queues.get(channel_id)

    if not queue:
        yield "event: error\ndata: No progress queue found\n\n"
        return

    logger.info(f"📡 [FullVideoAPI] Progress generator started for channel {channel_id}")

    try:
        yield "data: Kết nối streaming thành công. Bắt đầu xử lý video...\n\n"

        while True:
            message = await queue.get()

            if isinstance(message, dict):
                if "event" in message and message["event"] != "message":
                    yield f"event: {message['event']}\n"
                yield f"data: {message['data']}\n\n"
                logger.info(f"📡 [FullVideoAPI] Emitted event: {message.get('event', 'progress')}")
            else:
                yield message

            queue.task_done()

            if isinstance(message, dict) and message.get("event") in ["complete", "error"]:
                logger.info(f"📡 [FullVideoAPI] Progress generator ending due to event: {message.get('event')}")
                break

    except asyncio.CancelledError:
        logger.info(f"📡 [FullVideoAPI] Progress generator cancelled for channel {channel_id}")
        pass
    except Exception as e:
        logger.error(f"❌ [FullVideoAPI] Progress generator error: {e}")
        yield f"event: error\ndata: Stream error: {str(e)}\n\n"
    finally:
        progress_queues.pop(channel_id, None)
        logger.info(f"📡 [FullVideoAPI] Progress generator cleaned up for channel {channel_id}")

@router.post("/generate-full-video")
async def generate_full_video(
    prompt: str = Form(..., description="Mô tả video bạn muốn tạo"),
    script_data: Optional[str] = Form(None, description="Script data JSON (nếu có sẵn)"),
    images: List[UploadFile] = File(default=[], description="Hình ảnh tham khảo (tùy chọn)"),
    background_tasks: BackgroundTasks = None
):
    """
    Generate complete video from prompt using all agents (Analyzer -> Script -> Storyboard -> Audio -> Video)
    """
    input_image_paths = []
    state = None
    script_json = None

    logger.info("🚀 [FullVideoAPI] Starting full video generation...")
    logger.info(f"📋 [FullVideoAPI] Received prompt: {prompt[:100]}...")
    logger.info(f"🖼️ [FullVideoAPI] Received {len(images)} image files")

    # Parse script data if provided
    if script_data:
        try:
            script_json = json.loads(script_data)
            logger.info(f"📝 [FullVideoAPI] Loaded script with {len(script_json.get('storyboard', []))} scenes")
        except json.JSONDecodeError as e:
            logger.error(f"❌ [FullVideoAPI] Failed to parse script data: {e}")
            raise HTTPException(status_code=400, detail="Invalid script data format")

    try:
        # 1. Lưu images
        if images:
            logger.info(f"💾 [FullVideoAPI] Saving {len(images)} uploaded images...")
            input_image_paths = await save_upload_files(images)
            logger.info(f"✅ [FullVideoAPI] Images saved to: {input_image_paths}")

        # 2. Tạo state
        logger.info(f"🔧 [FullVideoAPI] Creating AppState...")
        state = AppState(prompt=prompt, input_image_paths=input_image_paths)
        logger.info(f"🆔 [FullVideoAPI] Created channel_id: {state.channel_id}")

        # 3. TẠO QUEUE
        queue = asyncio.Queue()
        progress_queues[state.channel_id] = queue

        await queue.put({"event": "progress", "data": "🚀 Khởi động hệ thống tạo video hoàn chỉnh..."})

        # 4. Helper emit progress
        async def emit_progress(message: str, event_type: str = "progress"):
            logger.info(f"📡 [FullVideoAPI] Progress: {message}")
            await queue.put({"event": event_type, "data": message})

        # Helper emit structured data
        async def emit_data(event_type: str, data: dict):
            logger.info(f"📡 [FullVideoAPI] Emitting {event_type} event")
            await queue.put({"event": event_type, "data": data})

        # 5. PHASE 1 & 2: ANALYZER + SCRIPT (nếu chưa có script)
        if not script_json:
            # ANALYZER AGENT
            logger.info(f"🔍 [FullVideoAPI] Running Analyzer Agent...")
            await emit_progress("🔍 Phân tích kịch bản video...")

            analyzer = AnalyzerAgent()
            state = await analyzer.run(state, progress_callback=emit_progress)

            await emit_progress("✅ Phân tích hoàn thành!")
            await emit_data("analysis_result", state.analysis_result or {})

            # SCRIPT AGENT
            logger.info(f"📝 [FullVideoAPI] Running Script Agent...")
            await emit_progress("📝 Tạo kịch bản chi tiết...")

            script_agent = ScriptAgent()
            state = await script_agent.run(state, progress_callback=emit_progress)

            script_json = state.script
            await emit_progress("✅ Kịch bản hoàn thành!")
            await emit_data("script", script_json or {})
        else:
            logger.info(f"📝 [FullVideoAPI] Using provided script data")
            await emit_progress("📝 Sử dụng kịch bản có sẵn...")
            await emit_data("script", script_json)

        # 6. PHASE 3: STORYBOARD AGENT
        logger.info(f"🎨 [FullVideoAPI] Running Storyboard Agent...")
        await emit_progress("🎨 Tạo hình ảnh cho từng cảnh...")

        storyboard_agent = StoryboardAgent()

        # Set progress callback for streaming
        storyboard_agent.set_progress_callback(lambda data: emit_progress(
            f"🎨 {data.get('message', 'Đang tạo hình ảnh...')}",
            "storyboard_progress"
        ))

        storyboard_result = await storyboard_agent.run_with_retry(
            storyboard=script_json.get("storyboard", []),
            style_info=state.analysis_result if hasattr(state, 'analysis_result') else {}
        )

        await emit_progress(f"✅ Đã tạo {storyboard_result.get('successful_generations', 0)}/{len(script_json.get('storyboard', []))} hình ảnh cảnh!")
        await emit_data("storyboard_result", storyboard_result)

        # 7. PHASE 4: AUDIO AGENT
        logger.info(f"🎙️ [FullVideoAPI] Running Audio Agent...")
        await emit_progress("🎙️ Tạo lời thoại cho video...")

        audio_agent = AudioAgent()

        # Set progress callback for streaming
        audio_agent.set_progress_callback(lambda data: emit_progress(
            f"🎙️ {data.get('message', 'Đang tạo audio...')}",
            "audio_progress"
        ))

        audio_result = await audio_agent.run_with_retry(
            narration=script_json.get("narration", ""),
            storyboard=script_json.get("storyboard", [])
        )

        await emit_progress(f"✅ Đã tạo {audio_result.get('successful_generations', 0)} đoạn audio!")
        await emit_data("audio_result", audio_result)

        # 8. PHASE 5: VIDEO AGENT
        logger.info(f"🎬 [FullVideoAPI] Running Video Agent...")
        await emit_progress("🎬 Dựng video hoàn chỉnh...")

        video_agent = VideoAgent()

        # Set progress callback for streaming
        video_agent.set_progress_callback(lambda data: emit_progress(
            f"🎬 {data.get('message', 'Đang dựng video...')}",
            "video_progress"
        ))

        video_result = await video_agent.run_with_retry(
            storyboard_images=storyboard_result.get("storyboard_images", []),
            audio_files=audio_result.get("audio_files", []),
            storyboard=script_json.get("storyboard", [])
        )

        final_video = video_result.get("final_video", {})

        await emit_progress("🎉 Video đã được tạo thành công!")
        await emit_data("video_result", video_result)

        # 9. FINAL SUMMARY
        summary = {
            "prompt": prompt,
            "analysis_result": state.analysis_result if hasattr(state, 'analysis_result') else None,
            "script": script_json,
            "storyboard": storyboard_result,
            "audio": audio_result,
            "video": video_result,
            "total_duration": final_video.get("duration_seconds", 0),
            "file_size": final_video.get("file_size_bytes", 0),
            "video_path": final_video.get("path", "")
        }

        await emit_progress("🎊 Tất cả các giai đoạn đã hoàn thành!")
        await emit_data("final_video", summary)

        # 10. Send completion event
        await queue.put({"event": "complete", "data": "Video generation completed successfully!"})

    except Exception as e:
        error_msg = f"❌ Lỗi: {str(e)}"
        logger.error(f"❌ [FullVideoAPI] {error_msg}")
        logger.error(f"❌ [FullVideoAPI] Full traceback: {traceback.format_exc()}")

        if state and state.channel_id in progress_queues:
            await progress_queues[state.channel_id].put({"event": "error", "data": error_msg})

        if state:
            state.add_progress(error_msg)

        raise HTTPException(status_code=500, detail=error_msg)

    finally:
        logger.info(f"🧹 [FullVideoAPI] Starting cleanup...")
        if input_image_paths:
            logger.info(f"🗑️ [FullVideoAPI] Scheduling cleanup for {len(input_image_paths)} files")
            background_tasks.add_task(cleanup_files, input_image_paths)

        logger.info(f"📊 [FullVideoAPI] Final state summary:")
        if state:
            logger.info(f"✅ [FullVideoAPI] Video generation completed successfully")

@router.get("/stream/{channel_id}")
async def stream_progress(channel_id: str):
    """Stream progress updates for video generation"""
    return StreamingResponse(
        progress_generator(channel_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )