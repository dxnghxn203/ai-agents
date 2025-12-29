from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.motion_gen.state import LottieState
from app.agents.motion_gen.nodes import (
    analyzer_agent,
    content_planner_agent,
    json_mapper_agent,
    human_approval_node,
    apply_user_edits,
    video_generator_agent
)


def create_motion_gen_graph():
    """Create the LangGraph workflow for Lottie motion generation"""

    # Create graph with state
    workflow = StateGraph(LottieState)

    # Add nodes
    workflow.add_node("analyzer", analyzer_agent)
    workflow.add_node("planner", content_planner_agent)
    workflow.add_node("mapper", json_mapper_agent)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("apply_edits", apply_user_edits)
    workflow.add_node("video_generator", video_generator_agent)

    # Define edges
    workflow.add_edge("analyzer", "planner")
    workflow.add_edge("planner", "mapper")
    workflow.add_edge("mapper", "video_generator")
    workflow.add_edge("video_generator", END)

    # Set entry point
    workflow.set_entry_point("analyzer")

    # Compile graph with memory
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


def get_app():
    """Get the compiled LangGraph app"""
    if not hasattr(get_app, "_app"):
        get_app._app = create_motion_gen_graph()
    return get_app._app