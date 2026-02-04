from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .logging_config import get_logger, start_pipeline_log
from .nodes.document_processor import document_processor
from .nodes.triage_agent import triage_agent
from .state import PipelineState

log = get_logger("graph")


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

    builder = StateGraph(PipelineState)

    # Add nodes
    builder.add_node("document_processor", document_processor)
    builder.add_node("triage_agent", triage_agent)
    builder.add_node("finalize", finalize)

    # Add edges
    # START -> document_processor (LLM #1: returns triage payloads directly)
    builder.add_edge(START, "document_processor")

    # document_processor returns Send objects that route to triage_agent or finalize
    # triage_agent handles create/update directly, then goes to finalize
    builder.add_edge("triage_agent", "finalize")

    # finalize -> END
    builder.add_edge("finalize", END)

    log.info("Pipeline graph compiled")
    return builder.compile()


# Create the compiled graph
pipeline_graph = create_pipeline_graph()


async def run_pipeline(
    trigger: str, document_content: list[dict] | None = None, document_id: str | None = None
) -> dict:
    """Run the pipeline on a trigger with optional document context."""
    import uuid

    # Start a new log file for this pipeline run
    log_file = start_pipeline_log()

    # Auto-generate document_id for tracking if not provided
    doc_id = document_id or f"cli-{uuid.uuid4().hex[:8]}"
    log.info(f"Starting pipeline for document: {doc_id}")
    log.info(f"Log file: {log_file}")

    initial_state: PipelineState = {
        "trigger": trigger,
        "document_id": doc_id,
        "document_content": document_content or [],
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
