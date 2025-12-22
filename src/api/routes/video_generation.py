from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List
import asyncio

from src.models.schemas import AppState
from src.utils.file_handler import save_upload_files, cleanup_files

router = APIRouter()

# Queue đơn giản để stream progress theo channel_id (in-memory, đủ cho dev)
progress_queues: dict[str, asyncio.Queue] = {}

async def progress_generator(channel_id: str):
    queue = asyncio.Queue()
    progress_queues[channel_id] = queue
    
    try:
        # Message khởi đầu
        yield "data: Kết nối streaming thành công. Bắt đầu xử lý...\n\n"
        
        await queue.put("data: Đã nhận yêu cầu tạo video\n\n")
        
        while True:
            message = await queue.get()
            if isinstance(message, dict):
                # Handle dict như trước
                if "event" in message and message["event"] != "message":
                    yield f"event: {message['event']}\n"
                yield f"data: {message['data']}\n\n"
            else:
                yield message  # String đã format sẵn
                
            queue.task_done()
            if "complete" in message or "error" in message:
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
    """
    Endpoint chính: Nhận prompt + images → xử lý → stream progress real-time
    """
    # Bước 1: Lưu images tạm
    input_image_paths = []
    try:
        if images:
            input_image_paths = await save_upload_files(images)
        
        # Bước 2: Tạo AppState
        state = AppState(
            prompt=prompt,
            input_image_paths=input_image_paths
        )
        
        # Thêm progress khởi đầu
        state.add_progress(f"Đã nhận prompt: {prompt[:60]}...")
        if input_image_paths:
            state.add_progress(f"Đã nhận {len(input_image_paths)} hình ảnh")

        # Bước 3: Thông báo qua queue (sau này sẽ trigger graph)
        queue = progress_queues.get(state.channel_id)
        if queue:
            await queue.put({"event": "progress", "data": f"Số ảnh upload: {len(input_image_paths)}"})
            await queue.put({"event": "progress", "data": "Đang chuẩn bị workflow... (sẽ có graph ở giai đoạn sau)"})
            await queue.put({"event": "progress", "data": "MVP input handling hoàn thành!"})

        # Giả lập xử lý lâu (sẽ thay bằng graph thật)
        await asyncio.sleep(2)
        await queue.put({"event": "complete", "data": "Xử lý input thành công (demo giai đoạn 2)"})
        await queue.put({"event": "video_url", "data": "https://example.com/demo-video.mp4"})  # Fake URL
        
    except Exception as e:
        error_msg = f"Lỗi: {str(e)}"
        queue = progress_queues.get(state.channel_id) if 'state' in locals() else None
        if queue:
            await queue.put({"event": "error", "data": error_msg})
        raise
    
    finally:
        # Dọn dẹp file tạm sau (có thể dùng background_tasks)
        if input_image_paths:
            background_tasks.add_task(cleanup_files, input_image_paths)

    # Trả về SSE stream
    return StreamingResponse(
        progress_generator(state.channel_id),
        media_type="text/event-stream"
    )