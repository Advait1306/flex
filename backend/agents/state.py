from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


def add(a: list, b: list) -> list:
    """Reducer that combines lists from parallel branches."""
    return a + b


class TodoItem(BaseModel):
    """A todo task item."""

    id: str
    title: str
    description: str | None = None
    parent_id: str | None = Field(default=None, description="ID of parent todo if this is a subtask")
    status: Literal["pending", "in_progress", "completed"] = "pending"


class NewTask(BaseModel):
    """A new task extracted from a document."""

    title: str = Field(description="A concise title for the task")
    description: str | None = Field(
        default=None,
        description="Description only if the user provides specific details about the task",
    )
    subtasks: list["NewTask"] | None = Field(
        default=None,
        description="Related sub-tasks if multiple related items are mentioned",
    )


NewTask.model_rebuild()


class TodoUpdate(BaseModel):
    """An update to an existing todo."""

    todo_id: str = Field(description="The ID of the todo to update (can be a parent or subtask)")
    title: str | None = Field(default=None, description="New title for the todo")
    description: str | None = Field(default=None, description="New description")
    status: Literal["pending", "in_progress", "completed"] | None = Field(
        default=None,
        description="New status: 'pending', 'in_progress', or 'completed'",
    )


class PipelineState(TypedDict):
    """Main pipeline state."""

    trigger: str  # Text content to analyze for tasks (primary input)
    document_id: str  # Internal tracking ID
    document_content: list[dict]  # Context document (can be empty)
    new_tasks: list[NewTask]
    update_tasks: list[TodoUpdate]
    created_todos: Annotated[list[TodoItem], add]
    updated_todos: Annotated[list[TodoItem], add]
    errors: Annotated[list[str], add]
    status: Literal["pending", "scanning", "routing", "processing", "completed", "failed"]


class TodoCreatorState(TypedDict):
    """State for todo creator branch."""

    task: NewTask


class TriageState(TypedDict):
    """State for triage agent branch."""

    update: TodoUpdate
