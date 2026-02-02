import json
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..config import get_llm
from ..logging_config import get_logger
from ..state import PipelineState
from ..storage import list_todos

log = get_logger("scanner")


class ExtractedTask(BaseModel):
    """A new task extracted from a document."""

    title: str = Field(description="A concise title for the task")
    description: str = Field(
        description="Detailed description of what needs to be done"
    )
    priority: str = Field(
        description="low, medium, or high based on urgency/importance"
    )
    source_text: str = Field(
        description="The exact text from the document that mentions this task"
    )


class TodoUpdate(BaseModel):
    """An update to an existing todo."""

    todo_id: str = Field(description="The ID of the existing todo to update")
    new_status: str | None = Field(
        default=None,
        description="New status for the todo: 'pending', 'in_progress', or 'completed'",
    )
    new_priority: str | None = Field(
        default=None,
        description="New priority for the todo: 'low', 'medium', or 'high'",
    )
    source_text: str = Field(
        default="", description="The exact text that indicates this update"
    )


class ScanResult(BaseModel):
    """Result of scanning a document for tasks."""

    new_tasks: list[ExtractedTask] = Field(
        default_factory=list, description="New tasks to create"
    )
    updates: list[TodoUpdate] = Field(
        default_factory=list, description="Updates to existing todos"
    )


SCANNER_SYSTEM_PROMPT = """You are a document analyzer that extracts actionable tasks and status updates.

Analyze the document content and identify:

1. NEW TASKS: Action items, todos, or tasks that should be created

2. UPDATES: References to existing tasks that need status changes or updates.
   Look for phrases indicating:
   - COMPLETION: "done", "finished", "completed", "close it", "can close", "shipped", "resolved", "fixed", "looks good"
   - IN PROGRESS: "working on", "started", "in progress", "picked up"
   - PRIORITY CHANGES: "urgent", "can wait", "low priority", "high priority"

   Valid status values: "pending", "in_progress", "completed"
   Valid priority values: "low", "medium", "high"

   When matching updates to existing todos, use fuzzy matching on titles.
   For example, "Analytics looks good" should match a todo titled "Set up analytics" or "Analytics dashboard".

Be liberal with updates - if someone says something "looks good" or "we can close it" referencing a topic, find the matching todo and mark it completed."""


def document_scanner(state: PipelineState) -> dict:
    """Scan document and extract tasks."""
    log.info(f"Scanning document: {state['document_id']}")

    llm = get_llm().with_structured_output(ScanResult, method="function_calling")

    # Get existing todos for context
    existing_todos = list_todos()
    existing_context = ""
    if existing_todos:
        existing_context = (
            f"\n\nExisting todos for reference:\n{json.dumps(existing_todos, indent=2)}"
        )
        log.info(f"Found {len(existing_todos)} existing todos for context")
        for t in existing_todos:
            log.info(f"  Existing: {t['id'][:8]}... - {t['title']} ({t['status']})")

    # Convert document content to text
    doc_content = state["document_content"]
    if isinstance(doc_content, list):
        # BlockNote format - extract text from blocks
        text_parts = []
        for block in doc_content:
            if isinstance(block, dict):
                content = block.get("content", [])
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
        doc_text = "\n".join(text_parts)
    else:
        doc_text = str(doc_content)

    log.debug(f"Document text length: {len(doc_text)} chars")

    if not doc_text.strip():
        log.warning("Document is empty")
        return {
            "new_tasks": [],
            "update_tasks": [],
            "status": "completed",
            "errors": ["Document is empty"],
        }

    messages = [
        SystemMessage(content=SCANNER_SYSTEM_PROMPT + existing_context),
        HumanMessage(content=f"Analyze this document:\n\n{doc_text}"),
    ]

    try:
        log.info("Invoking LLM for task extraction")
        result = cast(ScanResult, llm.invoke(messages))

        new_tasks = []
        for task in result.new_tasks:
            task_dict = task.model_dump()
            task_dict["source_document_id"] = state["document_id"]
            new_tasks.append(task_dict)

        updates = []
        for u in result.updates:
            log.info(f"Raw update from LLM: todo_id={u.todo_id}, new_status={u.new_status}, new_priority={u.new_priority}")
            # Build updates dict from explicit fields
            field_updates = {}
            if u.new_status:
                field_updates["status"] = u.new_status
            if u.new_priority:
                field_updates["priority"] = u.new_priority
            updates.append({
                "todo_id": u.todo_id,
                "updates": field_updates,
                "source_text": u.source_text,
            })

        log.info(f"Extracted {len(new_tasks)} new tasks, {len(updates)} updates")
        for upd in updates:
            log.info(f"  Update: {upd}")

        return {"new_tasks": new_tasks, "update_tasks": updates, "status": "routing"}
    except Exception as e:
        log.error(f"Scanner error: {e}")
        return {
            "new_tasks": [],
            "update_tasks": [],
            "status": "failed",
            "errors": [f"Scanner error: {str(e)}"],
        }
