from ..logging_config import get_logger
from ..state import TriageState
from ..storage import load_todo, save_todo

log = get_logger("triage")


def triage_agent(state: TriageState) -> dict:
    """Update an existing todo based on update instructions."""
    update = state["update"]
    todo_id = update.get("todo_id")

    log.info(f"Processing update for todo: {todo_id}")
    log.info(f"Update payload: {update}")

    if not todo_id:
        log.error("No todo_id provided for update")
        return {"updated_todos": [], "errors": ["No todo_id provided for update"]}

    try:
        existing_todo = load_todo(todo_id)

        if not existing_todo:
            log.warning(f"Todo not found: {todo_id}")
            return {"updated_todos": [], "errors": [f"Todo {todo_id} not found"]}

        # Apply updates
        updates = update.get("updates", {})
        log.info(f"Applying updates to todo: {updates}")

        for key, value in updates.items():
            old_value = existing_todo.get(key)
            existing_todo[key] = value
            log.info(f"  {key}: {old_value} -> {value}")

        # Track the update source
        existing_todo["last_update_source"] = update.get("source_text", "")

        saved_todo = save_todo(existing_todo)

        log.info(f"Updated todo: {todo_id} - new status: {saved_todo.get('status')}")

        return {"updated_todos": [saved_todo], "errors": []}
    except Exception as e:
        log.error(f"Failed to update todo {todo_id}: {e}")
        return {"updated_todos": [], "errors": [f"Failed to update todo {todo_id}: {str(e)}"]}
