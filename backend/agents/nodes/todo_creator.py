from ..storage import save_todo, generate_id
from ..state import TodoCreatorState
from ..logging_config import get_logger

log = get_logger("todo_creator")


def todo_creator(state: TodoCreatorState) -> dict:
    """Create a new todo from a task."""
    task = state["task"]
    title = task.get("title", "Untitled")

    log.info(f"Creating todo: {title}")

    try:
        todo = {
            "id": generate_id(),
            "title": title,
            "description": task.get("description", ""),
            "priority": task.get("priority", "medium"),
            "status": "pending",
            "source_document_id": task.get("source_document_id", ""),
            "source_text": task.get("source_text", ""),
        }

        saved_todo = save_todo(todo)

        log.info(f"Created todo: {saved_todo['id']} - {title}")

        return {
            "created_todos": [saved_todo],
            "errors": []
        }
    except Exception as e:
        log.error(f"Failed to create todo '{title}': {e}")
        return {
            "created_todos": [],
            "errors": [f"Failed to create todo '{title}': {str(e)}"]
        }
