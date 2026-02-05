from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.logging_config import get_logger
from models import TodoItem
from store import delete_todo, generate_id, list_todos, load_todo, save_todo

log = get_logger("api.todos")

router = APIRouter(prefix="/api", tags=["todos"])


class TodoCreate(BaseModel):
    title: str
    description: str | None = None
    parent_id: str | None = None


class TodoUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


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
