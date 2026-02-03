import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents import run_pipeline
from agents.logging_config import get_logger
from agents.state import TodoItem
from agents.storage import delete_todo, generate_id, list_todos, load_todo, save_todo

log = get_logger("api.pipeline")

router = APIRouter(prefix="/api", tags=["pipeline"])

# Storage path for documents
STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"
DOCUMENTS_FILE = STORAGE_DIR / "documents.json"


def load_documents() -> dict:
    """Load documents from storage."""
    if DOCUMENTS_FILE.exists():
        with open(DOCUMENTS_FILE, "r") as f:
            return json.load(f)
    return {"documents": {}, "order": []}


class PipelineRequest(BaseModel):
    trigger: str
    document_id: str | None = None  # Optional - loads document as context


class TodoCreate(BaseModel):
    title: str
    description: str | None = None
    parent_id: str | None = None


class TodoUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


@router.post("/pipeline/run")
async def run_pipeline_endpoint(request: PipelineRequest):
    """Run the agent pipeline on a trigger with optional document context."""
    log.info(f"Pipeline run requested with trigger: {request.trigger[:50]}...")

    # Load document content if document_id provided
    document_content = None
    if request.document_id:
        data = load_documents()
        document_content = data["documents"].get(request.document_id)
        if document_content is None:
            log.warning(f"Document not found: {request.document_id}")
            raise HTTPException(status_code=404, detail="Document not found")

    result = await run_pipeline(request.trigger, document_content, request.document_id)

    log.info(f"Pipeline completed: {len(result.get('created_todos', []))} created, {len(result.get('updated_todos', []))} updated")

    return result


@router.get("/todos")
async def get_todos():
    """Get all todos."""
    log.debug("Listing all todos")
    todos = list_todos()
    return {"todos": [t.model_dump(exclude_none=True) for t in todos]}


@router.get("/todos/{todo_id}")
async def get_todo(todo_id: str):
    """Get a specific todo."""
    log.debug(f"Getting todo: {todo_id}")
    todo = load_todo(todo_id)
    if not todo:
        log.warning(f"Todo not found: {todo_id}")
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo.model_dump(exclude_none=True)


@router.post("/todos")
async def create_todo(todo: TodoCreate):
    """Create a new todo manually."""
    log.info(f"Creating todo manually: {todo.title}")

    new_todo = TodoItem(
        id=generate_id(),
        title=todo.title,
        description=todo.description,
        parent_id=todo.parent_id,
        status="pending",
    )

    saved = save_todo(new_todo)
    log.info(f"Created todo: {saved.id}")
    return saved.model_dump(exclude_none=True)


@router.patch("/todos/{todo_id}")
async def update_todo(todo_id: str, updates: TodoUpdateRequest):
    """Update a todo."""
    log.info(f"Updating todo: {todo_id}")

    existing = load_todo(todo_id)
    if not existing:
        log.warning(f"Todo not found: {todo_id}")
        raise HTTPException(status_code=404, detail="Todo not found")

    # Build updated data
    updated_data = existing.model_dump()

    if updates.title is not None:
        updated_data["title"] = updates.title

    if updates.description is not None:
        updated_data["description"] = updates.description

    if updates.status is not None:
        updated_data["status"] = updates.status

    updated_todo = TodoItem.model_validate(updated_data)
    saved = save_todo(updated_todo)
    log.info(f"Updated todo: {todo_id}")
    return saved.model_dump(exclude_none=True)


@router.delete("/todos/{todo_id}")
async def delete_todo_endpoint(todo_id: str):
    """Delete a todo."""
    log.info(f"Deleting todo: {todo_id}")

    if delete_todo(todo_id):
        return {"status": "deleted"}

    log.warning(f"Todo not found for deletion: {todo_id}")
    raise HTTPException(status_code=404, detail="Todo not found")
