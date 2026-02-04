from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


def add(a: list, b: list) -> list:
    """Reducer that combines lists from parallel branches."""
    return a + b


class MentionedItem(BaseModel):
    """An item mentioned by the user that might become a task."""

    text: str  # What was mentioned
    intent: Literal["create", "update_status", "add_detail", "general"]
    status_hint: Literal["pending", "in_progress", "completed"] | None = None
    related_keywords: list[str] = []
    background_info: str | None = None  # Relevant context from document for this specific item


class FactItem(BaseModel):
    """A fact about the user stored in the knowledge base."""

    id: str
    fact: str
    category: Literal["preference", "personal", "work", "context", "other"] = "other"
    tags: list[str] = []  # Tags for multi-vector embeddings
    source_trigger: str | None = None
    created_at: str | None = None


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
        description="ONLY if user explicitly provided details - never invent a description",
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
    document_context: str  # Pre-extracted and truncated document text for context
    created_todos: Annotated[list[TodoItem], add]
    updated_todos: Annotated[list[TodoItem], add]
    errors: Annotated[list[str], add]
    status: Literal["pending", "scanning", "routing", "processing", "completed", "failed"]


class TriagePayload(TypedDict):
    """Payload sent to triage agent for a single mentioned item."""

    item: MentionedItem
