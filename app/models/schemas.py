from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
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


class ContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    PLACEHOLDER = "placeholder"


class TransformType(str, Enum):
    POSITION = "position"
    SCALE = "scale"
    ROTATION = "rotation"
    OPACITY = "opacity"


class LottieLayer(BaseModel):
    id: str
    name: str
    type: str
    visible: bool = True
    transform: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)


class PlaceholderInfo(BaseModel):
    layer_id: str
    name: str
    content_type: ContentType
    transform_editable: List[TransformType] = Field(default_factory=list)
    current_value: Optional[Any] = None
    placeholder_text: Optional[str] = None


class MappingPlan(BaseModel):
    text_mappings: Dict[str, str] = Field(default_factory=dict)  # layer_id -> text
    image_mappings: Dict[str, str] = Field(default_factory=dict)  # layer_id -> image_url/path
    transform_mappings: Dict[str, Dict[str, Any]] = Field(default_factory=dict)  # layer_id -> transform


class LottieGenRequest(BaseModel):
    lottie_template_id: str
    prompt: str
    conversation_id: str


class LottieResumeRequest(BaseModel):
    conversation_id: str
    edits: Dict[str, Any] = Field(default_factory=dict)


class TextEdit(BaseModel):
    text: Dict[str, str] = Field(default_factory=dict)


class ImageEdit(BaseModel):
    image: Dict[str, str] = Field(default_factory=dict)


class TransformEdit(BaseModel):
    transform: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class SSEEvent(BaseModel):
    event: str
    data: Dict[str, Any]
    conversation_id: str


class LottieGenResponse(BaseModel):
    conversation_id: str
    status: str
    message: str
    preview_url: Optional[str] = None
    lottie_json: Optional[Dict[str, Any]] = None
    video_url: Optional[str] = None


class LottieVideoGenParams(BaseModel):
    duration: float = Field(default=5.0, description="Video duration in seconds")
    fps: int = Field(default=30, description="Frames per second")
    width: int = Field(default=512, description="Video width in pixels")
    height: int = Field(default=512, description="Video height in pixels")
    background_color: str = Field(default="#000000", description="Background color in hex")


class LottieVideoGenRequest(BaseModel):
    video_generation_params: LottieVideoGenParams = Field(default_factory=LottieVideoGenParams)