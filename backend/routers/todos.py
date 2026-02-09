from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from logging_config import get_logger
from auth import verify_user
from store import create_todo as store_create_todo, update_todo as store_update_todo, delete_todo, list_todos, load_todo

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
async def get_todos(user: dict = Depends(verify_user)):
    """Get all todos."""
    log.debug("Listing all todos")
    todos = list_todos(user_id=user["id"])
    return {"todos": [t.model_dump(exclude_none=True) for t in todos]}


@router.get("/todos/{todo_id}")
async def get_todo(todo_id: str, user: dict = Depends(verify_user)):
    """Get a specific todo."""
    log.debug(f"Getting todo: {todo_id}")
    todo = load_todo(todo_id)
    if not todo:
        log.warning(f"Todo not found: {todo_id}")
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo.model_dump(exclude_none=True)


@router.post("/todos")
async def create_todo(todo: TodoCreate, user: dict = Depends(verify_user)):
    """Create a new todo manually."""
    log.info(f"Creating todo manually: {todo.title}")

    saved = store_create_todo(
        title=todo.title,
        description=todo.description,
        parent_id=todo.parent_id,
        user_id=user["id"],
    )
    log.info(f"Created todo: {saved.id}")
    return saved.model_dump(exclude_none=True)


@router.patch("/todos/{todo_id}")
async def update_todo(todo_id: str, updates: TodoUpdateRequest, user: dict = Depends(verify_user)):
    """Update a todo."""
    log.info(f"Updating todo: {todo_id}")

    try:
        saved = store_update_todo(
            todo_id,
            title=updates.title,
            description=updates.description,
            status=updates.status,
            user_id=user["id"],
        )
    except ValueError:
        log.warning(f"Todo not found: {todo_id}")
        raise HTTPException(status_code=404, detail="Todo not found")

    log.info(f"Updated todo: {todo_id}")
    return saved.model_dump(exclude_none=True)


@router.delete("/todos/{todo_id}")
async def delete_todo_endpoint(todo_id: str, user: dict = Depends(verify_user)):
    """Delete a todo."""
    log.info(f"Deleting todo: {todo_id}")

    if delete_todo(todo_id):
        return {"status": "deleted"}

    log.warning(f"Todo not found for deletion: {todo_id}")
    raise HTTPException(status_code=404, detail="Todo not found")
