from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

from models import TodoItem


def add(a: list, b: list) -> list:
    """Reducer that combines lists from parallel branches."""
    return a + b


class TriagePayload(BaseModel):
    """Payload sent to triage agent for a single item."""

    text: str
    context: str = ""


class NewTask(BaseModel):
    """A new task extracted from a document."""

    title: str = Field(description="A concise title for the task")
    description: str | None = Field(
        default=None,
        description="ONLY if user explicitly provided details - never invent a description",
    )
    subtasks: list["NewTask"] | None = Field(
        default=None,
        description="Related sub-tasks if multiple related items are mentioned",
    )


NewTask.model_rebuild()


class TodoUpdate(BaseModel):
    """An update to an existing todo."""

    todo_id: str = Field(
        description="The ID of the todo to update (can be a parent or subtask)"
    )
    title: str | None = Field(default=None, description="New title for the todo")
    description: str | None = Field(default=None, description="New description")
    status: Literal["pending", "in_progress", "completed"] | None = Field(
        default=None,
        description="New status: 'pending', 'in_progress', or 'completed'",
    )


# TypedDict is required by LangGraph's StateGraph to support Annotated reducers
# (e.g. merging lists from parallel fan-out branches). BaseModel won't work here.
class PipelineState(TypedDict):

    trigger: str
    document_id: str
    document_context: str
    created_todos: Annotated[list[TodoItem], add]
    updated_todos: Annotated[list[TodoItem], add]
    errors: Annotated[list[str], add]
    status: Literal[
        "pending", "scanning", "routing", "processing", "completed", "failed"
    ]
