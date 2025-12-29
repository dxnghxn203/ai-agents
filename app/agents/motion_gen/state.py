from typing import Dict, List, Any, Optional
from pydantic import BaseModel


class LottieState(BaseModel):
    """State for Lottie Motion Generation workflow"""

    # Core data
    original_lottie_json: Optional[Dict[str, Any]] = None
    generated_lottie_json: Optional[Dict[str, Any]] = None

    # Analysis results
    layer_structure: List[Dict[str, Any]] = []
    placeholders: List[Dict[str, Any]] = []

    # Planning
    mapping_plan: Optional[Dict[str, Any]] = None

    # Workflow tracking
    conversation_id: Optional[str] = None
    current_step: str = "initialized"
    error: Optional[str] = None

    # User interaction
    user_edits: Optional[Dict[str, Any]] = None
    requires_approval: bool = False

    # Metadata
    messages: List[Dict[str, str]] = []

    # Video generation
    video_path: Optional[str] = None
    video_generation_params: Optional[Dict[str, Any]] = None

    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.messages.append({"role": role, "content": content})

    def update_current_step(self, step: str):
        """Update current workflow step"""
        self.current_step = step

    def set_error(self, error: str):
        """Set error state"""
        self.error = error
        self.current_step = "error"

    def is_ready_for_next_step(self) -> bool:
        """Check if state is ready for next step"""
        if self.error:
            return False

        required_fields = {
            "analysis": self.original_lottie_json is not None,
            "planning": self.layer_structure is not None and len(self.layer_structure) > 0,
            "mapping": self.mapping_plan is not None,
            "generation": self.mapping_plan is not None,
            "approval": self.generated_lottie_json is not None,
            "video": self.generated_lottie_json is not None,
        }

        return required_fields.get(self.current_step, True)

    def get(self, key, default=None):
        """Get attribute value - for compatibility with dict-like access"""
        return getattr(self, key, default)

    def __getitem__(self, key):
        """Allow dictionary-style access"""
        return getattr(self, key)

    def __setitem__(self, key, value):
        """Allow dictionary-style assignment"""
        setattr(self, key, value)