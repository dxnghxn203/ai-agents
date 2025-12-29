"""Base Agent class for all video generation agents."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import asyncio

from ..models.manager import ModelManager
from ..models.text_llm import TextLLMManager
from ..models.tts import TTSManager
from ..models.image_gen import ImageGenManager

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all video generation agents."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.agent_id = f"{self.__class__.__name__.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.execution_time: Optional[float] = None
        self.retry_count = 0
        self.max_retries = self.config.get("max_retries", 3)

        # Initialize model managers
        self.model_manager = ModelManager()
        self.llm_manager = TextLLMManager(self.model_manager)
        self.tts_manager = TTSManager(self.model_manager)
        self.image_manager = ImageGenManager(self.model_manager)

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the agent's main functionality."""
        pass

    @abstractmethod
    def validate_input(self, **kwargs) -> bool:
        """Validate input parameters."""
        pass

    @abstractmethod
    def get_output_schema(self) -> Dict[str, Any]:
        """Get the expected output schema."""
        pass

    async def run_with_retry(self, **kwargs) -> Dict[str, Any]:
        """Run the agent with retry logic."""
        self.start_time = datetime.now()

        while self.retry_count <= self.max_retries:
            try:
                logger.info(f"Executing {self.__class__.__name__} (attempt {self.retry_count + 1})")

                # Validate input
                if not self.validate_input(**kwargs):
                    raise ValueError("Input validation failed")

                # Execute the agent
                result = await self.execute(**kwargs)

                # Add execution metadata
                self.end_time = datetime.now()
                self.execution_time = (self.end_time - self.start_time).total_seconds()

                result.update({
                    "agent_id": self.agent_id,
                    "agent_type": self.__class__.__name__,
                    "execution_time": self.execution_time,
                    "retry_count": self.retry_count,
                    "timestamp": self.end_time.isoformat()
                })

                logger.info(f"{self.__class__.__name__} completed successfully")
                return result

            except Exception as e:
                self.retry_count += 1
                logger.warning(f"{self.__class__.__name__} failed (attempt {self.retry_count}): {e}")

                if self.retry_count <= self.max_retries:
                    # Exponential backoff
                    await asyncio.sleep(2 ** self.retry_count)
                else:
                    # Max retries exceeded
                    self.end_time = datetime.now()
                    self.execution_time = (self.end_time - self.start_time).total_seconds()

                    logger.error(f"{self.__class__.__name__} failed after {self.max_retries} retries")
                    raise

    async def cleanup(self):
        """Cleanup resources after execution."""
        pass

    def get_cost_estimate(self, **kwargs) -> float:
        """Get estimated cost for this agent execution."""
        return 0.0

    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.__class__.__name__,
            "config": self.config,
            "max_retries": self.max_retries,
            "output_schema": self.get_output_schema()
        }


class ParallelAgent(BaseAgent):
    """Base class for agents that can run in parallel."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.dependencies = self.config.get("dependencies", [])
        self.parallel_group = self.config.get("parallel_group", "default")

    def can_run_parallel_with(self, other_agent: 'ParallelAgent') -> bool:
        """Check if this agent can run in parallel with another agent."""
        return (
            self.parallel_group == other_agent.parallel_group and
            not set(self.dependencies) & set(other_agent.dependencies)
        )


class SequentialAgent(BaseAgent):
    """Base class for agents that must run sequentially."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.prerequisites = self.config.get("prerequisites", [])

    def can_execute(self, completed_agents: List[str]) -> bool:
        """Check if this agent can execute given completed agents."""
        return all(prereq in completed_agents for prereq in self.prerequisites)


class StreamingAgent(BaseAgent):
    """Base class for agents that support streaming progress updates."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.progress_callback = None

    def set_progress_callback(self, callback):
        """Set progress callback function."""
        self.progress_callback = callback

    async def report_progress(self, progress: float, message: str):
        """Report progress updates."""
        if self.progress_callback:
            await self.progress_callback({
                "agent": self.__class__.__name__,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })

    @abstractmethod
    async def execute_with_streaming(self, **kwargs) -> Dict[str, Any]:
        """Execute with streaming progress updates."""
        pass

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Default execute calls streaming version."""
        return await self.execute_with_streaming(**kwargs)