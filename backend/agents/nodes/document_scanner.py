import json
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..config import get_llm
from ..logging_config import get_logger
from ..state import NewTask, PipelineState, TodoUpdate
from ..storage import list_todos

log = get_logger("scanner")


class ScanResult(BaseModel):
    """Result of scanning a document for tasks."""

    new_tasks: list[NewTask] = Field(
        default_factory=list, description="New tasks to create"
    )
    updates: list[TodoUpdate] = Field(
        default_factory=list, description="Updates to existing todos"
    )


SCANNER_SYSTEM_PROMPT = """You are a task analyzer that extracts tasks and status updates from user input.

The user's message is the primary input to analyze. If document context is provided, use it to understand references and background, but extract tasks from what the user explicitly says.

IMPORTANT RULES:
- ALWAYS prefer updating existing todos over creating new ones
- If the user's message relates to ANY existing todo (even loosely), create an UPDATE not a new task
- NEVER invent or decompose tasks - only extract what the user explicitly mentions
- Subtasks should ONLY be created when the user explicitly lists multiple related items in a single message

Return:

1. NEW TASKS (new_tasks): Only for genuinely new work not related to existing todos
   - title: A concise title matching what the user said
   - description: Only if the user provided specific details (don't invent)
   - subtasks: Only if the user explicitly mentioned multiple related items (NEVER decompose a task yourself)

2. UPDATES (updates): Changes to existing todos - USE THIS LIBERALLY
   - todo_id: The ID of the existing todo to update (match by topic/context, not exact title)
   - status: "pending", "in_progress", or "completed"

   Status indicators:
   - COMPLETED: "done", "finished", "completed", "shipped", "resolved", "fixed", "looks good"
   - IN PROGRESS: "working on", "started", "found", "interviewing", "looking into", "researching"

EXAMPLES:
- Existing todo: "Hire designer" → User says "Found 3 designers, interviewing today" → UPDATE status to "in_progress"
- Existing todo: "Set up analytics" → User says "Analytics looks good" → UPDATE status to "completed"
- User says "Need to buy groceries and pick up laundry" → ONE new task with TWO subtasks (user listed both)
- User says "Need to buy groceries" → ONE new task, NO subtasks (don't decompose into "make list", "go to store", etc.)"""


def extract_text_from_blocks(blocks: list[dict]) -> str:
    """Extract text content from BlockNote blocks."""
    if not blocks:
        return ""
    text_parts = []
    for block in blocks:
        if isinstance(block, dict):
            content = block.get("content", [])
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
    return "\n".join(text_parts)


def document_scanner(state: PipelineState) -> dict:
    """Scan trigger text and extract tasks, using document as optional context."""
    log.info(f"Scanning trigger for document: {state['document_id']}")

    llm = get_llm().with_structured_output(ScanResult, method="function_calling")

    # Get existing todos for context (flat structure - subtasks have parent_id)
    existing_todos = list_todos()
    existing_context = ""
    if existing_todos:
        todos_data = []
        for t in existing_todos:
            todo_info: dict = {"id": t.id, "title": t.title, "status": t.status}
            if t.parent_id:
                todo_info["parent_id"] = t.parent_id
            todos_data.append(todo_info)
        existing_context = f"\n\nExisting todos (update these if the message relates to them):\n{json.dumps(todos_data, indent=2)}"
        log.info(f"Found {len(existing_todos)} existing todos for context")
        for t in existing_todos:
            parent_info = f" (subtask of {t.parent_id[:8]}...)" if t.parent_id else ""
            log.info(f"  Existing: {t.id[:8]}... - {t.title} ({t.status}){parent_info}")

    # Get trigger text (primary input)
    trigger_text = state["trigger"]
    log.debug(f"Trigger text length: {len(trigger_text)} chars")

    if not trigger_text.strip():
        log.warning("Trigger text is empty")
        return {
            "new_tasks": [],
            "update_tasks": [],
            "status": "completed",
            "errors": ["Trigger text is empty"],
        }

    # Extract document context (optional)
    doc_text = extract_text_from_blocks(state.get("document_content", []))
    if doc_text:
        log.debug(f"Document context length: {len(doc_text)} chars")

    # Build the human message with trigger and optional document context
    human_content = f"Analyze this for tasks:\n\n{trigger_text}"
    if doc_text:
        human_content += f"\n\nDocument context:\n{doc_text}"

    messages = [
        SystemMessage(content=SCANNER_SYSTEM_PROMPT + existing_context),
        HumanMessage(content=human_content),
    ]

    try:
        log.info("Invoking LLM for task extraction")
        result = cast(ScanResult, llm.invoke(messages))

        for u in result.updates:
            log.info(f"Raw update from LLM: todo_id={u.todo_id}, title={u.title}, status={u.status}")

        log.info(f"Extracted {len(result.new_tasks)} new tasks, {len(result.updates)} updates")

        return {"new_tasks": result.new_tasks, "update_tasks": result.updates, "status": "routing"}
    except Exception as e:
        log.error(f"Scanner error: {e}")
        return {
            "new_tasks": [],
            "update_tasks": [],
            "status": "failed",
            "errors": [f"Scanner error: {str(e)}"],
        }
