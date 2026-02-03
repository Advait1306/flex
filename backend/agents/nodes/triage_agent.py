import json
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..config import get_llm
from ..logging_config import get_logger
from ..qdrant_store import generate_id, load_todo, save_todo
from ..search import SearchResult, search_todos as _search_todos
from ..state import MentionedItem, NewTask, TodoItem, TriagePayload

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
    tags: list[str] = Field(
        default_factory=list,
        description="2-5 key searchable tags/topics for this todo (e.g., 'authentication', 'JWT', 'login flow'). Only for create/update actions.",
    )


@tool
def search_todos(query: str) -> str:
    """Search for existing todos by semantic similarity and keyword matching.

    Use this to find todos that might be related to the current item.
    Try different search terms to find relevant matches - search by topic,
    technology, feature name, or action type.

    Args:
        query: Search terms to find matching todos (e.g., "authentication", "login bug", "JWT")

    Returns:
        JSON list of matching todos with their IDs, titles, status, and relevance scores
    """
    results: list[SearchResult] = _search_todos(query, limit=10)

    if not results:
        return "No matching todos found."

    todos_data = []
    for result in results:
        t = result.todo
        todo_info: dict = {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "relevance_score": round(result.score, 3),
        }
        if t.parent_id:
            todo_info["parent_id"] = t.parent_id
        if t.description:
            todo_info["description"] = t.description
        todos_data.append(todo_info)

    return json.dumps(todos_data, indent=2)


TRIAGE_AGENT_PROMPT = """You are a triage agent that decides how to handle a single mentioned item.

You have access to a search_todos tool to find existing todos. Use it to search for related todos before making a decision.

Your job is to decide ONE action:
- "create": Create a new task (only if this is genuinely new work not covered by existing todos)
- "update": Update an existing todo (PREFERRED - match by topic/keywords, not exact title)
- "ignore": No action needed (general info, already handled, or not actionable)

WORKFLOW:
1. First, use search_todos to find potentially related todos. Try different search terms based on the item's content.
2. Review the search results to see if any existing todo matches.
3. Make your decision based on what you found.

IMPORTANT:
- ALWAYS search before deciding - don't assume there are no existing todos
- ALWAYS prefer "update" over "create" if there's ANY related existing todo
- Match existing todos by topic/keywords, not exact title match
- Use the item's intent and status_hint to guide your decision
- If intent is "update_status", you MUST find a matching todo to update (or ignore if no match)
- If intent is "create", still search to check if an existing todo covers this topic
- NEVER invent or make up descriptions - only include a description if the user explicitly provided details

For "update" action, provide:
- todo_id: The ID of the existing todo to update
- status: New status if changing (pending/in_progress/completed)
- title: New title only if it should change
- description: ONLY if the user explicitly provided new details (never invent)
- tags: 2-5 key searchable tags/topics (technologies, features, actions mentioned)

For "create" action, provide:
- new_task with title only (no description unless the user explicitly provided details)
- tags: 2-5 key searchable tags/topics (technologies, features, actions mentioned)

Tags help with future searches. Extract key concepts like:
- Technologies: "JWT", "React", "PostgreSQL"
- Features: "authentication", "login flow", "user profile"
- Actions: "bug fix", "refactor", "performance optimization"
- Domains: "security", "frontend", "database"
"""

MAX_TOOL_CALLS = 5


def triage_agent(state: TriagePayload) -> dict:
    """Triage a single mentioned item using tool-calling to search for existing todos."""
    item: MentionedItem = state["item"]

    log.info(f"Triaging item: {item.text} (intent={item.intent})")

    # Build human message
    item_json = item.model_dump_json(indent=2)
    human_content = f"Item to triage:\n{item_json}"

    messages = [
        SystemMessage(content=TRIAGE_AGENT_PROMPT),
        HumanMessage(content=human_content),
    ]

    # Get LLM with both tools and structured output bound
    llm = get_llm()
    tools = [search_todos, TriageDecision]
    llm_with_tools = llm.bind_tools(tools)

    try:
        # Agent loop - let LLM call tools until it returns a TriageDecision
        decision: TriageDecision | None = None

        for i in range(MAX_TOOL_CALLS):
            log.info(f"Agent loop iteration {i + 1}")

            response: AIMessage = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                log.warning("LLM returned no tool calls, prompting for decision")
                messages.append(HumanMessage(content="Please make your triage decision now using the TriageDecision tool."))
                continue

            for tool_call in response.tool_calls:
                log.info(f"Tool call: {tool_call['name']}({tool_call['args']})")

                if tool_call["name"] == "search_todos":
                    result = search_todos.invoke(tool_call["args"])
                    # Count results for console, full results in file log
                    try:
                        result_count = len(json.loads(result)) if result != "No matching todos found." else 0
                    except json.JSONDecodeError:
                        result_count = 0
                    log.info(f"Search returned {result_count} results")
                    log.debug(f"Search results:\n{result}")

                    tool_message = ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"],
                    )
                    messages.append(tool_message)

                elif tool_call["name"] == "TriageDecision":
                    # LLM returned its decision
                    decision = TriageDecision.model_validate(tool_call["args"])
                    break

            if decision:
                break

        if not decision:
            log.error("LLM did not return a decision after max iterations")
            return {
                "created_todos": [],
                "updated_todos": [],
                "errors": ["Triage agent did not return a decision"],
            }

        log.info(f"Triage decision: {decision.action} - {decision.reason}")

        if decision.action == "create" and decision.new_task:
            return _create_todo(decision.new_task, tags=decision.tags)

        elif decision.action == "update" and decision.todo_id:
            return _update_todo(
                decision.todo_id,
                title=decision.title,
                description=decision.description,
                status=decision.status,
                tags=decision.tags,
            )

        else:
            log.info(f"Ignoring item: {item.text}")
            return {"created_todos": [], "updated_todos": [], "errors": []}

    except Exception as e:
        log.error(f"Triage agent error: {e}")
        return {
            "created_todos": [],
            "updated_todos": [],
            "errors": [f"Triage error for '{item.text}': {str(e)}"],
        }


def _create_todo(task: NewTask, tags: list[str] | None = None) -> dict:
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
        save_todo(parent_todo, tags=tags)
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
                # Subtasks inherit parent tags if none specified
                save_todo(subtask_todo, tags=tags)
                created_todos.append(subtask_todo)
                log.info(
                    f"Created subtask: {subtask_todo.id} - {subtask.title} (parent: {parent_id})"
                )

        return {"created_todos": created_todos, "updated_todos": [], "errors": []}
    except Exception as e:
        log.error(f"Failed to create todo '{task.title}': {e}")
        return {
            "created_todos": [],
            "updated_todos": [],
            "errors": [f"Failed to create todo '{task.title}': {str(e)}"],
        }


def _update_todo(
    todo_id: str,
    title: str | None = None,
    description: str | None = None,
    status: Literal["pending", "in_progress", "completed"] | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Update an existing todo."""
    log.info(f"Updating todo: {todo_id}")

    try:
        existing_todo = load_todo(todo_id)

        if not existing_todo:
            log.warning(f"Todo not found: {todo_id}")
            return {
                "created_todos": [],
                "updated_todos": [],
                "errors": [f"Todo {todo_id} not found"],
            }

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
        saved_todo = save_todo(updated_todo, tags=tags)

        log.info(f"Updated todo: {todo_id} - new status: {saved_todo.status}")

        return {"created_todos": [], "updated_todos": [saved_todo], "errors": []}
    except Exception as e:
        log.error(f"Failed to update todo {todo_id}: {e}")
        return {
            "created_todos": [],
            "updated_todos": [],
            "errors": [f"Failed to update todo {todo_id}: {str(e)}"],
        }
