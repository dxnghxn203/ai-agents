from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List
import asyncio

from src.models.schemas import AppState
from src.utils.file_handler import save_upload_files, cleanup_files

from src.agents.analyzer import AnalyzerAgent
from src.agents.script import ScriptAgent

router = APIRouter()

# Queue đơn giản để stream progress theo channel_id (in-memory, đủ cho dev)
progress_queues: dict[str, asyncio.Queue] = {}

async def progress_generator(channel_id: str):
    queue: asyncio.Queue = asyncio.Queue()
    progress_queues[channel_id] = queue  # Tạo queue NGAY khi generator được gọi
    
    try:
        yield "data: Kết nối streaming thành công. Bắt đầu xử lý...\n\n"
        
        # Message khởi đầu
        await queue.put("data: Đã nhận yêu cầu tạo video\n\n")
        
        while True:
            message = await queue.get()
            if isinstance(message, dict):
                if "event" in message and message["event"] != "message":
                    yield f"event: {message['event']}\n"
                yield f"data: {message['data']}\n\n"
            else:
                yield message
                
            queue.task_done()
            
            # Kiểm tra điều kiện kết thúc
            if isinstance(message, dict) and message.get("event") in ["complete", "error"]:
                break
                
    except asyncio.CancelledError:
        pass
    finally:
        progress_queues.pop(channel_id, None)
        
@router.post("/generate-video")
async def generate_video(
    prompt: str = Form(..., description="Mô tả video bạn muốn tạo"),
    images: List[UploadFile] = File(default=[], description="Hình ảnh tham khảo (tùy chọn)"),
    background_tasks: BackgroundTasks = None
):
    input_image_paths = []
    state = None
    
    try:
        # 1. Lưu images
        if images:
            input_image_paths = await save_upload_files(images)
        
        # 2. Tạo state
        state = AppState(prompt=prompt, input_image_paths=input_image_paths)
        state.add_progress(f"📥 Đã nhận prompt: {prompt[:60]}...")
        if input_image_paths:
            state.add_progress(f"🖼️ Đã nhận {len(input_image_paths)} hình ảnh")

        # 3. TẠO QUEUE NGAY TẠI ĐÂY TRƯỚC KHI XỬ LÝ (QUAN TRỌNG!)
        queue = asyncio.Queue()
        progress_queues[state.channel_id] = queue

        # Emit khởi đầu
        await queue.put({"event": "progress", "data": "🚀 Khởi động hệ thống..."})
        await queue.put({"event": "progress", "data": f"Đã nhận {len(input_image_paths)} ảnh tham khảo"})

        # 4. Helper emit progress
        async def emit_progress(message: str):
            await queue.put({"event": "progress", "data": message})

        # 5. CHẠY ANALYZER AGENT
        await emit_progress("🔍 Bắt đầu Analyzer Agent...")
        analyzer = AnalyzerAgent()
        state = await analyzer.run(state, progress_callback=emit_progress)

        await emit_progress("✅ Analyzer Agent hoàn thành!")
        await queue.put({"event": "analysis_result", "data": state.analysis_result or {}})

        # 6. CHẠY SCRIPT AGENT
        await emit_progress("📝 Bắt đầu Script Agent...")
        script_agent = ScriptAgent()
        state = await script_agent.run(state, progress_callback=emit_progress)

        await emit_progress("✅ Script Agent hoàn thành!")
        await queue.put({"event": "script", "data": state.script or {}})
        await queue.put({"event": "complete", "data": "Giai đoạn 4 thành công!"})

    except Exception as e:
        error_msg = f"❌ Lỗi: {str(e)}"
        if state and state.channel_id in progress_queues:
            await progress_queues[state.channel_id].put({"event": "error", "data": error_msg})
        if state:
            state.add_progress(error_msg)
        raise

    finally:
        if input_image_paths:
            background_tasks.add_task(cleanup_files, input_image_paths)

    # Trả về stream (queue đã sẵn sàng)
    return StreamingResponse(
        progress_generator(state.channel_id),
        media_type="text/event-stream"
    )