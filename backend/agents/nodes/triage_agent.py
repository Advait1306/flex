from ..logging_config import get_logger
from ..state import TodoItem, TriageState
from ..storage import load_todo, save_todo

log = get_logger("triage")


def triage_agent(state: TriageState) -> dict:
    """Update an existing todo based on update instructions."""
    update = state["update"]
    todo_id = update.todo_id

    log.info(f"Processing update for todo: {todo_id}")

    try:
        existing_todo = load_todo(todo_id)

        if not existing_todo:
            log.warning(f"Todo not found: {todo_id}")
            return {"updated_todos": [], "errors": [f"Todo {todo_id} not found"]}

        # Build updated fields
        updated_data = existing_todo.model_dump()

        if update.title is not None:
            log.info(f"  title: {existing_todo.title} -> {update.title}")
            updated_data["title"] = update.title

        if update.description is not None:
            log.info(f"  description: {existing_todo.description} -> {update.description}")
            updated_data["description"] = update.description

        if update.status is not None:
            log.info(f"  status: {existing_todo.status} -> {update.status}")
            updated_data["status"] = update.status

        updated_todo = TodoItem.model_validate(updated_data)
        saved_todo = save_todo(updated_todo)

        log.info(f"Updated todo: {todo_id} - new status: {saved_todo.status}")

        return {"updated_todos": [saved_todo], "errors": []}
    except Exception as e:
        log.error(f"Failed to update todo {todo_id}: {e}")
        return {"updated_todos": [], "errors": [f"Failed to update todo {todo_id}: {str(e)}"]}
