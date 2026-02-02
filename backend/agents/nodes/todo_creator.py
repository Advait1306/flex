from ..logging_config import get_logger
from ..state import NewTask, TodoCreatorState, TodoItem
from ..storage import generate_id, save_todo

log = get_logger("todo_creator")


def todo_creator(state: TodoCreatorState) -> dict:
    """Create todos from a task, flattening any subtasks into separate todos."""
    task = state["task"]

    log.info(f"Creating todo: {task.title}")

    try:
        created_todos: list[TodoItem] = []

        # Create the parent todo
        parent_id = generate_id()
        parent_todo = TodoItem(
            id=parent_id,
            title=task.title,
            description=task.description,
            status="pending",
        )
        save_todo(parent_todo)
        created_todos.append(parent_todo)
        log.info(f"Created todo: {parent_id} - {task.title}")

        # Create subtasks as separate todos with parent_id
        if task.subtasks:
            for subtask in task.subtasks:
                subtask_todo = TodoItem(
                    id=generate_id(),
                    title=subtask.title,
                    description=subtask.description,
                    parent_id=parent_id,
                    status="pending",
                )
                save_todo(subtask_todo)
                created_todos.append(subtask_todo)
                log.info(f"Created subtask: {subtask_todo.id} - {subtask.title} (parent: {parent_id})")

        return {"created_todos": created_todos, "errors": []}
    except Exception as e:
        log.error(f"Failed to create todo '{task.title}': {e}")
        return {"created_todos": [], "errors": [f"Failed to create todo '{task.title}': {str(e)}"]}
