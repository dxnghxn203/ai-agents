"""Graph State Management for LangGraph Multi-Agent System."""

from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime
from enum import Enum
import json


class AgentStatus(Enum):
    """Agent execution status."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class GraphState(TypedDict):
    """Main graph state shared across all agents."""
    # Input parameters
    prompt: str
    input_images: List[str]
    channel_id: str

    # Analysis results
    analysis_result: Optional[Dict[str, Any]]
    style_preferences: Dict[str, Any]
    technical_specs: Dict[str, Any]

    # Script and storyboard
    narration: Optional[str]
    storyboard: Optional[List[Dict[str, Any]]]
    scene_descriptions: List[str]

    # Agent states
    agent_status: Dict[str, AgentStatus]
    agent_results: Dict[str, Any]
    agent_errors: Dict[str, str]

    # Generation results
    audio_result: Optional[Dict[str, Any]]
    visual_result: Optional[Dict[str, Any]]
    camera_result: Optional[Dict[str, Any]]
    final_result: Optional[Dict[str, Any]]

    # Progress tracking
    progress_percentage: float
    current_step: str
    total_steps: int
    completed_steps: int

    # Metadata
    start_time: datetime
    end_time: Optional[datetime]
    generation_time: Optional[float]
    cost_estimates: Dict[str, float]

    # Configuration
    config: Dict[str, Any]


class AgentState(TypedDict):
    """Individual agent state."""
    agent_id: str
    agent_type: str
    status: AgentStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    execution_time: Optional[float]
    retry_count: int
    max_retries: int


class StateManager:
    """Manages graph state persistence and updates."""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self._local_cache: Dict[str, GraphState] = {}

    def create_state(
        self,
        prompt: str,
        input_images: List[str],
        channel_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> GraphState:
        """Create new graph state."""
        return GraphState(
            # Input parameters
            prompt=prompt,
            input_images=input_images or [],
            channel_id=channel_id,

            # Analysis results
            analysis_result=None,
            style_preferences={},
            technical_specs={},

            # Script and storyboard
            narration=None,
            storyboard=None,
            scene_descriptions=[],

            # Agent states
            agent_status={},
            agent_results={},
            agent_errors={},

            # Generation results
            audio_result=None,
            visual_result=None,
            camera_result=None,
            final_result=None,

            # Progress tracking
            progress_percentage=0.0,
            current_step="initialization",
            total_steps=7,  # Total workflow steps
            completed_steps=0,

            # Metadata
            start_time=datetime.now(),
            end_time=None,
            generation_time=None,
            cost_estimates={},

            # Configuration
            config=config or {}
        )

    def update_agent_status(
        self,
        state: GraphState,
        agent_id: str,
        status: AgentStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> GraphState:
        """Update agent status in state."""
        state["agent_status"][agent_id] = status

        if result:
            state["agent_results"][agent_id] = result

        if error:
            state["agent_errors"][agent_id] = error

        # Update progress
        self._update_progress(state)

        return state

    def _update_progress(self, state: GraphState):
        """Update progress based on agent statuses."""
        total_agents = len([
            agent for agent in ["analyzer", "script", "audio", "visual", "camera", "merge"]
            if agent in state["config"].get("enabled_agents", [
                "analyzer", "script", "audio", "visual", "camera", "merge"
            ])
        ])

        completed_agents = len([
            status for status in state["agent_status"].values()
            if status == AgentStatus.COMPLETED
        ])

        state["completed_steps"] = completed_agents
        state["progress_percentage"] = (completed_agents / total_agents) * 100 if total_agents > 0 else 0

    def save_state(self, state: GraphState) -> bool:
        """Save state to persistent storage."""
        try:
            state_json = self._serialize_state(state)

            if self.redis_client:
                # Save to Redis with expiration
                self.redis_client.setex(
                    f"graph_state:{state['channel_id']}",
                    3600,  # 1 hour expiration
                    state_json
                )

            # Also cache locally
            self._local_cache[state["channel_id"]] = state

            return True

        except Exception as e:
            print(f"Failed to save state: {e}")
            return False

    def load_state(self, channel_id: str) -> Optional[GraphState]:
        """Load state from persistent storage."""
        try:
            # Try local cache first
            if channel_id in self._local_cache:
                return self._local_cache[channel_id]

            # Try Redis
            if self.redis_client:
                state_json = self.redis_client.get(f"graph_state:{channel_id}")
                if state_json:
                    state = self._deserialize_state(state_json)
                    self._local_cache[channel_id] = state
                    return state

            return None

        except Exception as e:
            print(f"Failed to load state: {e}")
            return None

    def _serialize_state(self, state: GraphState) -> str:
        """Serialize state to JSON."""
        serializable_state = state.copy()

        # Convert datetime objects to strings
        if serializable_state.get("start_time"):
            serializable_state["start_time"] = serializable_state["start_time"].isoformat()

        if serializable_state.get("end_time"):
            serializable_state["end_time"] = serializable_state["end_time"].isoformat()

        # Convert enums to strings
        if "agent_status" in serializable_state:
            serializable_state["agent_status"] = {
                k: v.value if isinstance(v, AgentStatus) else v
                for k, v in serializable_state["agent_status"].items()
            }

        return json.dumps(serializable_state)

    def _deserialize_state(self, state_json: str) -> GraphState:
        """Deserialize state from JSON."""
        data = json.loads(state_json)

        # Convert datetime strings back to datetime objects
        if data.get("start_time"):
            data["start_time"] = datetime.fromisoformat(data["start_time"])

        if data.get("end_time"):
            data["end_time"] = datetime.fromisoformat(data["end_time"])

        # Convert strings back to enums
        if "agent_status" in data:
            data["agent_status"] = {
                k: AgentStatus(v) if isinstance(v, str) else v
                for k, v in data["agent_status"].items()
            }

        return data

    def delete_state(self, channel_id: str) -> bool:
        """Delete state from storage."""
        try:
            if self.redis_client:
                self.redis_client.delete(f"graph_state:{channel_id}")

            if channel_id in self._local_cache:
                del self._local_cache[channel_id]

            return True

        except Exception as e:
            print(f"Failed to delete state: {e}")
            return False


# Global state manager instance
state_manager = StateManager()