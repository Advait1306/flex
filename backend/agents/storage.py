import json
import uuid
from pathlib import Path
from filelock import FileLock
from .state import TaskItem
from .logging_config import get_logger

log = get_logger("storage")

STORAGE_DIR = Path(__file__).parent.parent.parent / "storage" / "todos"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def generate_id() -> str:
    """Generate a unique ID for a todo."""
    return str(uuid.uuid4())


def get_todo_path(todo_id: str) -> Path:
    """Get the file path for a todo."""
    return STORAGE_DIR / f"{todo_id}.json"


def save_todo(todo: dict) -> dict:
    """Save a todo to storage."""
    if "id" not in todo:
        todo["id"] = generate_id()

    path = get_todo_path(todo["id"])
    lock_path = path.with_suffix(".lock")

    log.info(f"Saving todo: {todo['id']} - {todo.get('title', 'Untitled')}")

    with FileLock(lock_path):
        with open(path, "w") as f:
            json.dump(todo, f, indent=2)

    log.debug(f"Todo saved to: {path}")
    return todo


def load_todo(todo_id: str) -> dict | None:
    """Load a todo from storage."""
    path = get_todo_path(todo_id)

    if not path.exists():
        log.warning(f"Todo not found: {todo_id}")
        return None

    lock_path = path.with_suffix(".lock")

    log.debug(f"Loading todo: {todo_id}")

    with FileLock(lock_path):
        with open(path, "r") as f:
            return json.load(f)


def list_todos() -> list[dict]:
    """List all todos."""
    todos = []
    for path in STORAGE_DIR.glob("*.json"):
        try:
            with open(path, "r") as f:
                todos.append(json.load(f))
        except (json.JSONDecodeError, IOError) as e:
            log.error(f"Failed to load todo from {path}: {e}")
            continue

    log.info(f"Listed {len(todos)} todos")
    return todos


def delete_todo(todo_id: str) -> bool:
    """Delete a todo."""
    path = get_todo_path(todo_id)
    lock_path = path.with_suffix(".lock")

    if path.exists():
        path.unlink()
        if lock_path.exists():
            lock_path.unlink()
        log.info(f"Deleted todo: {todo_id}")
        return True

    log.warning(f"Todo not found for deletion: {todo_id}")
    return False


def find_todo_by_title(title: str) -> dict | None:
    """Find a todo by title (case-insensitive partial match)."""
    title_lower = title.lower()
    for todo in list_todos():
        if title_lower in todo.get("title", "").lower():
            log.debug(f"Found todo by title '{title}': {todo['id']}")
            return todo
    log.debug(f"No todo found with title: {title}")
    return None
