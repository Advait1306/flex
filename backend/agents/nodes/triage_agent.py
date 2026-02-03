import json
from typing import Literal, cast

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..config import get_llm
from ..logging_config import get_logger
from ..state import MentionedItem, NewTask, TodoItem, TriagePayload
from ..storage import generate_id, list_todos, load_todo, save_todo

log = get_logger("triage_agent")


class TriageDecision(BaseModel):
    """Decision made by triage agent for a single item."""

    action: Literal["create", "update", "ignore"] = Field(
        description="What to do with this item"
    )
    # For create action
    new_task: NewTask | None = Field(
        default=None,
        description="New task to create (only if action is 'create')",
    )
    # For update action
    todo_id: str | None = Field(
        default=None,
        description="ID of existing todo to update (only if action is 'update')",
    )
    status: Literal["pending", "in_progress", "completed"] | None = Field(
        default=None,
        description="New status for the todo (only if action is 'update')",
    )
    title: str | None = Field(
        default=None,
        description="New title for the todo (only if action is 'update' and title should change)",
    )
    description: str | None = Field(
        default=None,
        description="New/updated description (only if action is 'update' and adding detail)",
    )
    reason: str = Field(description="Brief explanation of the decision")


TRIAGE_AGENT_PROMPT = """You are a triage agent that decides how to handle a single mentioned item.

You will receive:
1. A single item the user mentioned (with intent classification and keywords)
2. Optional background context
3. List of existing todos

Your job is to decide ONE action:
- "create": Create a new task (only if this is genuinely new work not covered by existing todos)
- "update": Update an existing todo (PREFERRED - match by topic/keywords, not exact title)
- "ignore": No action needed (general info, already handled, or not actionable)

IMPORTANT:
- ALWAYS prefer "update" over "create" if there's ANY related existing todo
- Match existing todos by topic/keywords, not exact title match
- Use the item's intent and status_hint to guide your decision
- If intent is "update_status", you MUST find a matching todo to update (or ignore if no match)
- If intent is "create", still check if an existing todo covers this topic
- NEVER invent or make up descriptions - only include a description if the user explicitly provided details

For "update" action, provide:
- todo_id: The ID of the existing todo to update
- status: New status if changing (pending/in_progress/completed)
- title: New title only if it should change
- description: ONLY if the user explicitly provided new details (never invent)

For "create" action, provide:
- new_task with title only (no description unless the user explicitly provided details)"""


def triage_agent(state: TriagePayload) -> dict:
    """Triage a single mentioned item, then create or update todo directly (LLM #2)."""
    item: MentionedItem = state["item"]

    log.info(f"Triaging item: {item.text} (intent={item.intent})")

    # Fetch existing todos for matching
    existing_todos = list_todos()
    existing_context = ""
    if existing_todos:
        todos_data = []
        for t in existing_todos:
            todo_info: dict = {"id": t.id, "title": t.title, "status": t.status}
            if t.parent_id:
                todo_info["parent_id"] = t.parent_id
            if t.description:
                todo_info["description"] = t.description
            todos_data.append(todo_info)
        existing_context = f"\n\nExisting todos (prefer updating these):\n{json.dumps(todos_data, indent=2)}"
        log.info(f"Found {len(existing_todos)} existing todos for matching")

    # Build human message
    item_json = item.model_dump_json(indent=2)
    human_content = f"Item to triage:\n{item_json}"

    llm = get_llm().with_structured_output(TriageDecision, method="function_calling")

    messages = [
        SystemMessage(content=TRIAGE_AGENT_PROMPT + existing_context),
        HumanMessage(content=human_content),
    ]

    try:
        log.info("Invoking LLM for triage decision")
        decision = cast(TriageDecision, llm.invoke(messages))

        log.info(f"Triage decision: {decision.action} - {decision.reason}")

        if decision.action == "create" and decision.new_task:
            return _create_todo(decision.new_task)

        elif decision.action == "update" and decision.todo_id:
            return _update_todo(
                decision.todo_id,
                title=decision.title,
                description=decision.description,
                status=decision.status,
            )

        else:
            log.info(f"Ignoring item: {item.text}")
            return {"created_todos": [], "updated_todos": [], "errors": []}

    except Exception as e:
        log.error(f"Triage agent error: {e}")
        return {"created_todos": [], "updated_todos": [], "errors": [f"Triage error for '{item.text}': {str(e)}"]}


def _create_todo(task: NewTask) -> dict:
    """Create a new todo from the task."""
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

        return {"created_todos": created_todos, "updated_todos": [], "errors": []}
    except Exception as e:
        log.error(f"Failed to create todo '{task.title}': {e}")
        return {"created_todos": [], "updated_todos": [], "errors": [f"Failed to create todo '{task.title}': {str(e)}"]}


def _update_todo(
    todo_id: str,
    title: str | None = None,
    description: str | None = None,
    status: Literal["pending", "in_progress", "completed"] | None = None,
) -> dict:
    """Update an existing todo."""
    log.info(f"Updating todo: {todo_id}")

    try:
        existing_todo = load_todo(todo_id)

        if not existing_todo:
            log.warning(f"Todo not found: {todo_id}")
            return {"created_todos": [], "updated_todos": [], "errors": [f"Todo {todo_id} not found"]}

        # Build updated fields
        updated_data = existing_todo.model_dump()

        if title is not None:
            log.info(f"  title: {existing_todo.title} -> {title}")
            updated_data["title"] = title

        if description is not None:
            log.info(f"  description: {existing_todo.description} -> {description}")
            updated_data["description"] = description

        if status is not None:
            log.info(f"  status: {existing_todo.status} -> {status}")
            updated_data["status"] = status

        updated_todo = TodoItem.model_validate(updated_data)
        saved_todo = save_todo(updated_todo)

        log.info(f"Updated todo: {todo_id} - new status: {saved_todo.status}")

        return {"created_todos": [], "updated_todos": [saved_todo], "errors": []}
    except Exception as e:
        log.error(f"Failed to update todo {todo_id}: {e}")
        return {"created_todos": [], "updated_todos": [], "errors": [f"Failed to update todo {todo_id}: {str(e)}"]}
