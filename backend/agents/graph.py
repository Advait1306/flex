from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from .logging_config import get_logger
from .nodes.document_scanner import document_scanner
from .nodes.todo_creator import todo_creator
from .nodes.triage_agent import triage_agent
from .state import PipelineState

log = get_logger("graph")


def route_tasks(state: PipelineState) -> list[Send]:
    """Route tasks to appropriate handlers via fan-out."""
    sends = []

    new_tasks = state.get("new_tasks", [])
    update_tasks = state.get("update_tasks", [])

    log.info(f"Routing: {len(new_tasks)} new tasks, {len(update_tasks)} updates")

    # Fan out to todo creators for new tasks
    for task in new_tasks:
        log.debug(f"Routing new task: {task.title}")
        sends.append(Send("todo_creator", {"task": task}))

    # Fan out to triage agents for updates
    for update in update_tasks:
        log.debug(f"Routing update for todo: {update.todo_id}")
        sends.append(Send("triage_agent", {"update": update}))

    # If no tasks, go directly to end
    if not sends:
        log.info("No tasks to process, finalizing")
        return [Send("finalize", {})]

    return sends


def finalize(state: PipelineState) -> dict:
    """Finalize the pipeline."""
    created = len(state.get("created_todos", []))
    updated = len(state.get("updated_todos", []))
    errors = state.get("errors", [])

    log.info(
        f"Pipeline complete: {created} created, {updated} updated, {len(errors)} errors"
    )

    if errors:
        for error in errors:
            log.error(f"Pipeline error: {error}")

    return {"status": "completed"}


def create_pipeline_graph() -> CompiledStateGraph:
    """Create and compile the pipeline graph."""
    log.info("Creating pipeline graph")

    # Build the graph
    builder = StateGraph(PipelineState)

    # Add nodes
    builder.add_node("document_scanner", document_scanner)
    builder.add_node("todo_creator", todo_creator)
    builder.add_node("triage_agent", triage_agent)
    builder.add_node("finalize", finalize)

    # Add edges
    builder.add_edge(START, "document_scanner")
    builder.add_conditional_edges("document_scanner", route_tasks)
    builder.add_edge("todo_creator", "finalize")
    builder.add_edge("triage_agent", "finalize")
    builder.add_edge("finalize", END)

    log.info("Pipeline graph compiled")
    return builder.compile()


# Create the compiled graph
pipeline_graph = create_pipeline_graph()


async def run_pipeline(trigger: str, document_content: list[dict] | None = None, document_id: str | None = None) -> dict:
    """Run the pipeline on a trigger with optional document context."""
    import uuid

    # Auto-generate document_id for tracking if not provided
    doc_id = document_id or f"cli-{uuid.uuid4().hex[:8]}"
    log.info(f"Starting pipeline for document: {doc_id}")

    initial_state: PipelineState = {
        "trigger": trigger,
        "document_id": doc_id,
        "document_content": document_content or [],
        "new_tasks": [],
        "update_tasks": [],
        "created_todos": [],
        "updated_todos": [],
        "errors": [],
        "status": "pending",
    }

    result = await pipeline_graph.ainvoke(initial_state)

    log.info(f"Pipeline finished for document: {doc_id}")

    # Convert TodoItem models to dicts for JSON response
    created_todos = [t.model_dump(exclude_none=True) for t in result.get("created_todos", [])]
    updated_todos = [t.model_dump(exclude_none=True) for t in result.get("updated_todos", [])]

    return {
        "document_id": doc_id,
        "created_todos": created_todos,
        "updated_todos": updated_todos,
        "errors": result.get("errors", []),
        "status": result.get("status", "completed"),
    }
