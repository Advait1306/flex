import json
import uuid
from pathlib import Path

from .logging_config import get_logger
from .state import TodoItem

log = get_logger("storage")

STORAGE_DIR = Path(__file__).parent.parent.parent / "storage" / "todos"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def generate_id() -> str:
    """Generate a unique ID for a todo."""
    return str(uuid.uuid4())


def get_todo_path(todo_id: str) -> Path:
    """Get the file path for a todo."""
    return STORAGE_DIR / f"{todo_id}.json"


def save_todo(todo: TodoItem) -> TodoItem:
    """Save a todo to storage."""
    path = get_todo_path(todo.id)
    log.info(f"Saving todo: {todo.id} - {todo.title}")

    with open(path, "w") as f:
        json.dump(todo.model_dump(exclude_none=True), f, indent=2)

    log.debug(f"Todo saved to: {path}")
    return todo


def load_todo(todo_id: str) -> TodoItem | None:
    """Load a todo from storage."""
    path = get_todo_path(todo_id)

    if not path.exists():
        log.warning(f"Todo not found: {todo_id}")
        return None

    log.debug(f"Loading todo: {todo_id}")

    with open(path, "r") as f:
        data = json.load(f)
        return TodoItem.model_validate(data)


def list_todos() -> list[TodoItem]:
    """List all todos."""
    todos = []
    for path in STORAGE_DIR.glob("*.json"):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                todos.append(TodoItem.model_validate(data))
        except (json.JSONDecodeError, IOError) as e:
            log.error(f"Failed to load todo from {path}: {e}")
            continue

    log.info(f"Listed {len(todos)} todos")
    return todos


def delete_todo(todo_id: str) -> bool:
    """Delete a todo."""
    path = get_todo_path(todo_id)

    if path.exists():
        path.unlink()
        log.info(f"Deleted todo: {todo_id}")
        return True

    log.warning(f"Todo not found for deletion: {todo_id}")
    return False


def find_todo_by_title(title: str) -> TodoItem | None:
    """Find a todo by title (case-insensitive partial match)."""
    title_lower = title.lower()
    for todo in list_todos():
        if title_lower in todo.title.lower():
            log.debug(f"Found todo by title '{title}': {todo.id}")
            return todo
    log.debug(f"No todo found with title: {title}")
    return None
