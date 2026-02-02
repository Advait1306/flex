from typing import TypedDict, Literal, Annotated
from pydantic import BaseModel
import operator


def add(a: list, b: list) -> list:
    """Reducer that combines lists from parallel branches."""
    return a + b


class TaskItem(BaseModel):
    """A todo task item."""
    id: str
    title: str
    description: str = ""
    priority: Literal["low", "medium", "high"] = "medium"
    status: Literal["pending", "in_progress", "completed"] = "pending"
    source_document_id: str = ""
    source_text: str = ""


class UpdateItem(BaseModel):
    """An update to an existing todo."""
    todo_id: str
    updates: dict  # Fields to update
    source_text: str = ""


class PipelineState(TypedDict):
    """Main pipeline state."""
    document_id: str
    document_content: list[dict]
    new_tasks: list[TaskItem]
    update_tasks: list[UpdateItem]
    created_todos: Annotated[list[dict], add]
    updated_todos: Annotated[list[dict], add]
    errors: Annotated[list[str], add]
    status: Literal["pending", "scanning", "routing", "processing", "completed", "failed"]


class TodoCreatorState(TypedDict):
    """State for todo creator branch."""
    task: dict
    result: dict | None
    error: str | None


class TriageState(TypedDict):
    """State for triage agent branch."""
    update: dict
    existing_todo: dict | None
    result: dict | None
    error: str | None
