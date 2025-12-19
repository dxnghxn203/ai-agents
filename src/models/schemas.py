from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

class VideoGenerateInput(BaseModel):
    prompt: str
    # images sẽ được xử lý sau upload, lưu path tạm

class TaskOutput(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    error: Optional[str] = None
    artifact_paths: List[str] = []

class AppState(BaseModel):
    # Identification
    channel_id: str = str(uuid.uuid4())
    
    # Input
    prompt: str
    input_image_paths: List[str] = []
    
    # Intermediate results
    analysis_result: Optional[Dict[str, Any]] = None
    script: Optional[Dict[str, Any]] = None
    
    # Agent outputs
    tasks: Dict[str, TaskOutput] = {}
    
    # Progress tracking
    progress_events: List[str] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Final output
    final_video_path: Optional[str] = None
    final_video_url: Optional[str] = None
    
    def add_progress(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.progress_events.append(f"[{timestamp}] {message}")