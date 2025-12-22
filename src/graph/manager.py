"""LangGraph Multi-Agent Workflow Manager."""

from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import asyncio
import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import GraphState, AgentStatus, StateManager
from ..agents import AnalyzerAgent, ScriptAgent, AudioAgent, VisualAgent, CameraAgent, MergeAgent

logger = logging.getLogger(__name__)


class GraphManager:
    """Manages LangGraph workflows and agent coordination."""

    def __init__(self):
        self.state_manager = StateManager()
        self.graph: Optional[StateGraph] = None
        self.checkpointer = MemorySaver()
        self._initialize_graph()
        self._setup_agent_hooks()

    def _initialize_graph(self):
        """Initialize the LangGraph workflow."""
        # Create the graph
        self.graph = StateGraph(GraphState)

        # Add nodes for each agent
        self.graph.add_node("analyzer", self._analyzer_node)
        self.graph.add_node("script", self._script_node)
        self.graph.add_node("parallel_execution", self._parallel_execution_node)
        self.graph.add_node("merge", self._merge_node)
        self.graph.add_node("finalization", self._finalization_node)

        # Define the workflow edges
        self.graph.add_edge("analyzer", "script")
        self.graph.add_edge("script", "parallel_execution")
        self.graph.add_edge("parallel_execution", "merge")
        self.graph.add_edge("merge", "finalization")
        self.graph.add_edge("finalization", END)

        # Set the entry point
        self.graph.set_entry_point("analyzer")

        # Compile the graph
        self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)

    def _setup_agent_hooks(self):
        """Setup agent lifecycle hooks."""
        self.agent_hooks = {
            "before_execution": [],
            "after_execution": [],
            "on_error": [],
            "on_retry": []
        }

    def add_hook(self, hook_type: str, callback: Callable):
        """Add a hook for agent lifecycle events."""
        if hook_type in self.agent_hooks:
            self.agent_hooks[hook_type].append(callback)

    async def execute_workflow(
        self,
        prompt: str,
        input_images: List[str] = None,
        config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute the complete video generation workflow."""
        channel_id = config.get("channel_id") if config else f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create initial state
        state = self.state_manager.create_state(
            prompt=prompt,
            input_images=input_images or [],
            channel_id=channel_id,
            config=config or {}
        )

        # Save initial state
        self.state_manager.save_state(state)

        try:
            # Execute the graph
            logger.info(f"Starting workflow for channel {channel_id}")

            # Run the graph
            final_state = await self._run_graph_async(state)

            # Update final state
            final_state["end_time"] = datetime.now()
            final_state["generation_time"] = (
                final_state["end_time"] - final_state["start_time"]
            ).total_seconds()

            # Save final state
            self.state_manager.save_state(final_state)

            return final_state

        except Exception as e:
            logger.error(f"Workflow failed for channel {channel_id}: {e}")

            # Update state with error
            state["agent_status"]["workflow"] = AgentStatus.FAILED
            state["agent_errors"]["workflow"] = str(e)
            state["end_time"] = datetime.now()

            self.state_manager.save_state(state)

            raise

    async def _run_graph_async(self, state: GraphState) -> GraphState:
        """Run the graph asynchronously."""
        # Since LangGraph doesn't natively support async, we run in executor
        loop = asyncio.get_event_loop()

        # Create thread-safe execution
        result = await loop.run_in_executor(
            None,
            self.compiled_graph.invoke,
            state,
            {"configurable": {"thread_id": state["channel_id"]}}
        )

        return result

    def _analyzer_node(self, state: GraphState) -> GraphState:
        """Analyzer agent node."""
        return self._execute_agent_node(
            state=state,
            agent_name="analyzer",
            agent_class=AnalyzerAgent,
            input_key="prompt",
            output_key="analysis_result"
        )

    def _script_node(self, state: GraphState) -> GraphState:
        """Script agent node."""
        return self._execute_agent_node(
            state=state,
            agent_name="script",
            agent_class=ScriptAgent,
            input_key="analysis_result",
            output_key="narration"
        )

    def _parallel_execution_node(self, state: GraphState) -> GraphState:
        """Execute audio, visual, and camera agents in parallel."""
        import asyncio

        # Create parallel tasks
        tasks = []

        # Audio agent task
        if state["config"].get("enable_audio", True):
            tasks.append(self._execute_agent_async(
                state=state,
                agent_name="audio",
                agent_class=AudioAgent,
                input_data={"narration": state["narration"], "storyboard": state.get("storyboard", [])}
            ))

        # Visual agent task
        if state["config"].get("enable_visual", True):
            tasks.append(self._execute_agent_async(
                state=state,
                agent_name="visual",
                agent_class=VisualAgent,
                input_data={"storyboard": state.get("storyboard", []), "analysis": state["analysis_result"]}
            ))

        # Camera agent task
        if state["config"].get("enable_camera", True):
            tasks.append(self._execute_agent_async(
                state=state,
                agent_name="camera",
                agent_class=CameraAgent,
                input_data={"storyboard": state.get("storyboard", [])}
            ))

        # Wait for all tasks to complete
        if tasks:
            results = asyncio.run(asyncio.gather(*tasks, return_exceptions=True))

            # Update state with results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Agent task failed: {result}")
                    continue

                agent_name = list(state["config"].get("enabled_agents", ["audio", "visual", "camera"]))[i]
                state[f"{agent_name}_result"] = result

        return state

    async def _execute_agent_async(
        self,
        state: GraphState,
        agent_name: str,
        agent_class,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an agent asynchronously."""
        try:
            # Call before execution hooks
            await self._call_hooks("before_execution", agent_name, input_data)

            # Initialize and execute agent
            agent = agent_class()
            result = await agent.execute(**input_data)

            # Call after execution hooks
            await self._call_hooks("after_execution", agent_name, result)

            return result

        except Exception as e:
            logger.error(f"{agent_name} agent failed: {e}")
            await self._call_hooks("on_error", agent_name, e)
            raise

    def _merge_node(self, state: GraphState) -> GraphState:
        """Merge agent node."""
        return self._execute_agent_node(
            state=state,
            agent_name="merge",
            agent_class=MergeAgent,
            input_data={
                "audio_result": state.get("audio_result"),
                "visual_result": state.get("visual_result"),
                "camera_result": state.get("camera_result"),
                "storyboard": state.get("storyboard", [])
            },
            output_key="final_result"
        )

    def _finalization_node(self, state: GraphState) -> GraphState:
        """Finalization node - cleanup and final processing."""
        logger.info(f"Finalizing workflow for {state['channel_id']}")

        # Update final status
        state["current_step"] = "completed"
        state["progress_percentage"] = 100.0

        # Perform any final cleanup
        # This could include temporary file cleanup, logging, etc.

        return state

    def _execute_agent_node(
        self,
        state: GraphState,
        agent_name: str,
        agent_class,
        input_key: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        output_key: Optional[str] = None
    ) -> GraphState:
        """Execute a single agent node."""
        try:
            logger.info(f"Executing {agent_name} agent")

            # Update state
            state["current_step"] = agent_name
            state = self.state_manager.update_agent_status(
                state, agent_name, AgentStatus.RUNNING
            )

            # Prepare input data
            if input_data is None and input_key:
                input_data = {input_key: state.get(input_key)}

            # Execute agent
            agent = agent_class()
            result = agent.execute(**(input_data or {}))

            # Update state with result
            if output_key:
                state[output_key] = result

            state = self.state_manager.update_agent_status(
                state, agent_name, AgentStatus.COMPLETED, result
            )

            # Save state
            self.state_manager.save_state(state)

            return state

        except Exception as e:
            logger.error(f"{agent_name} agent failed: {e}")

            state = self.state_manager.update_agent_status(
                state, agent_name, AgentStatus.FAILED, error=str(e)
            )

            self.state_manager.save_state(state)
            raise

    async def _call_hooks(self, hook_type: str, agent_name: str, data: Any):
        """Call agent lifecycle hooks."""
        hooks = self.agent_hooks.get(hook_type, [])
        for hook in hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(agent_name, data)
                else:
                    hook(agent_name, data)
            except Exception as e:
                logger.warning(f"Hook {hook_type} failed: {e}")

    def get_workflow_state(self, channel_id: str) -> Optional[GraphState]:
        """Get current workflow state."""
        return self.state_manager.load_state(channel_id)

    def cancel_workflow(self, channel_id: str) -> bool:
        """Cancel a running workflow."""
        try:
            state = self.state_manager.load_state(channel_id)
            if state:
                state["agent_status"]["workflow"] = AgentStatus.FAILED
                state["agent_errors"]["workflow"] = "Workflow cancelled by user"
                state["end_time"] = datetime.now()
                self.state_manager.save_state(state)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cancel workflow: {e}")
            return False

    def list_active_workflows(self) -> List[str]:
        """List all currently active workflows."""
        # This would require tracking active workflows in the state manager
        # For now, return empty list
        return []