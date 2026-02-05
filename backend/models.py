from typing import Literal

from pydantic import BaseModel, Field


class TodoItem(BaseModel):
    """A todo task item."""

    id: str
    title: str
    description: str | None = None
    parent_id: str | None = Field(
        default=None, description="ID of parent todo if this is a subtask"
    )
    status: Literal["pending", "in_progress", "completed", "cancelled"] = "pending"
    created_at: str | None = None
    updated_at: str | None = None


class FactItem(BaseModel):
    """A fact about the user stored in the knowledge base."""

    id: str
    fact: str
    category: Literal["preference", "personal", "work", "context", "other"] = "other"
    tags: list[str] = []
    created_at: str | None = None


class TriagePayload(BaseModel):
    """Payload sent to triage agent for a single item."""

    text: str
    context: str = ""
