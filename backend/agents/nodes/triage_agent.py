import json
import uuid
from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..config import get_llm
from ..logging_config import get_logger
from ..qdrant_store import (
    FactSearchResult,
    generate_id,
    load_todo,
    save_todo,
    save_fact as _save_fact,
    search_facts as _search_facts,
)
from ..search import SearchResult, search_todos as _search_todos
from ..state import FactItem, MentionedItem, NewTask, TodoItem, TriagePayload

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


@tool
def search_facts(query: str) -> str:
    """Search for known facts about the user by semantic similarity and keyword matching.

    Use this to find relevant context about the user that might inform your decision.
    Facts include user preferences, personal info, work context, etc.

    Args:
        query: Search terms to find matching facts (e.g., "preferences", "work", "programming")

    Returns:
        JSON list of matching facts with their categories and relevance scores
    """
    results: list[FactSearchResult] = _search_facts(query, limit=5)

    if not results:
        return "No matching facts found."

    facts_data = []
    for result in results:
        f = result.fact
        fact_info: dict = {
            "fact": f.fact,
            "category": f.category,
            "relevance_score": round(result.score, 3),
        }
        if f.tags:
            fact_info["tags"] = f.tags
        facts_data.append(fact_info)

    return json.dumps(facts_data, indent=2)


@tool
def save_fact(
    fact: str,
    category: Literal["preference", "personal", "work", "context", "other"],
    tags: list[str],
) -> str:
    """Save a fact about the user for future reference.

    Use this when you find information worth remembering that is NOT task-related.
    Only call this AFTER searching todos to confirm there's no related task.

    Args:
        fact: The fact to remember about the user
        category: Category of the fact
            - "preference": User preferences, styles, likes/dislikes
            - "personal": Personal info about the user
            - "work": Work-related context, projects, team info
            - "context": General knowledge, guidelines, rules, ideas
            - "other": Anything else worth remembering
        tags: Keywords for semantic search (e.g., ["budget", "billboard", "marketing"])

    Returns:
        Confirmation that the fact was saved
    """
    return f"Fact will be saved: {fact}"


@tool
def do_nothing(reason: str) -> str:
    """Use when no action is needed - no todo to create/update and no fact worth saving.

    Args:
        reason: Brief explanation of why no action is needed
    """
    return f"No action taken: {reason}"


TRIAGE_AGENT_PROMPT = """You are a triage agent that decides how to handle a SINGLE mentioned item.

You receive ONE item at a time. Your job is to search for context and make a decision.

You have access to these tools:
1. **search_todos** - Find existing todos that might be related to the current item
2. **search_facts** - Find known facts/context about the user
3. **save_fact** - Save information worth remembering (NOT task-related)
4. **do_nothing** - When no action is needed at all
5. **TriageDecision** - Make your final decision about the item

WORKFLOW:
1. ALWAYS search_todos first to find potentially related todos
2. Optionally search_facts for relevant context
3. Then EITHER:
   a. Call TriageDecision (create/update/ignore) for task-related items
   b. Call save_fact then do_nothing for non-task info worth remembering
   c. Call do_nothing for pure greetings/thanks

DECISION LOGIC:

If there IS a related todo:
- Use TriageDecision with action="update" to add info to that todo
- Example: "Budget is $5000" + existing billboard todo → update todo description

If there is NO related todo:
- For actionable items → TriageDecision with action="create"
- For valuable context/info → save_fact, then do_nothing
- For pure greetings/thanks → do_nothing only

EXAMPLES:
- "The billboard budget is $5000" + existing "Buy billboards" todo
  → search_todos → TriageDecision(action="update", description="Budget: $5000")

- "The billboard budget is $5000" + NO related todo
  → search_todos → save_fact("Billboard budget is $5000", "context", ["budget", "billboard"])
  → do_nothing("Saved as fact, no related todo")

- "Our company was founded in 2020"
  → search_todos → save_fact("Company founded in 2020", "context", ["company", "history"])
  → do_nothing("No related todo, saved as fact")

- "I'm a software engineer"
  → search_todos → save_fact("User is a software engineer", "personal", ["profession"])
  → do_nothing("Personal info saved")

- "Buy groceries"
  → search_todos → TriageDecision(action="create", new_task={title: "Buy groceries"})

CRITICAL RULES:
- ALWAYS search_todos before making any decision
- Prefer "update" over "create" if there's a related existing todo
- Only save_fact for info that's worth remembering but NOT task-related
- Don't save_fact for pure greetings ("Thanks!", "Hello!")
- Do NOT invent tasks beyond what was explicitly mentioned
- Do NOT break down items into sub-tasks

For TriageDecision "create" action:
- new_task.title should be close to the original item text (don't embellish)
- new_task.description only if user provided details or relevant facts exist
- tags: 2-5 key searchable concepts

For TriageDecision "update" action:
- todo_id: The ID of the existing todo to update
- Only update fields that need changing
- description: Write the COMPLETE new description - preserve ALL existing info and add the new info
- NEVER remove existing information unless explicitly asked
- If the new info is already in the todo, use do_nothing instead (no redundant updates)
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
    tools = [search_todos, search_facts, save_fact, do_nothing, TriageDecision]
    llm_with_tools = llm.bind_tools(tools)

    # Track facts to save and whether agent is done
    facts_to_save: list[dict] = []
    done = False

    try:
        # Agent loop - let LLM call tools until it returns a TriageDecision or do_nothing
        decision: TriageDecision | None = None

        for i in range(MAX_TOOL_CALLS):
            log.info(f"Agent loop iteration {i + 1}")

            response: AIMessage = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                log.warning("LLM returned no tool calls, prompting for decision")
                messages.append(HumanMessage(content="Please make your decision using TriageDecision or do_nothing."))
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
                    log.info(f"Todo search returned {result_count} results")
                    log.debug(f"Todo search results:\n{result}")

                    tool_message = ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"],
                    )
                    messages.append(tool_message)

                elif tool_call["name"] == "search_facts":
                    result = search_facts.invoke(tool_call["args"])
                    # Count results for console, full results in file log
                    try:
                        result_count = len(json.loads(result)) if result != "No matching facts found." else 0
                    except json.JSONDecodeError:
                        result_count = 0
                    log.info(f"Fact search returned {result_count} results")
                    log.debug(f"Fact search results:\n{result}")

                    tool_message = ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"],
                    )
                    messages.append(tool_message)

                elif tool_call["name"] == "save_fact":
                    fact_text = tool_call["args"].get("fact", "")
                    category = tool_call["args"].get("category", "other")
                    tags = tool_call["args"].get("tags", [])

                    log.info(f"save_fact called: {fact_text[:50]}... category={category}")

                    # Queue fact for saving (we'll save after loop completes)
                    facts_to_save.append({
                        "fact": fact_text,
                        "category": category,
                        "tags": tags,
                    })

                    tool_message = ToolMessage(
                        content=f"Fact queued for saving: {fact_text}",
                        tool_call_id=tool_call["id"],
                    )
                    messages.append(tool_message)

                elif tool_call["name"] == "do_nothing":
                    reason = tool_call["args"].get("reason", "No reason provided")
                    log.info(f"do_nothing called: {reason}")

                    tool_message = ToolMessage(
                        content=f"Acknowledged: {reason}",
                        tool_call_id=tool_call["id"],
                    )
                    messages.append(tool_message)
                    done = True
                    break

                elif tool_call["name"] == "TriageDecision":
                    # LLM returned its decision
                    decision = TriageDecision.model_validate(tool_call["args"])
                    done = True
                    break

            if done:
                break

        # Save any queued facts
        for fact_data in facts_to_save:
            fact_item = FactItem(
                id=str(uuid.uuid4()),
                fact=fact_data["fact"],
                category=fact_data["category"],
                tags=fact_data["tags"],
                source_trigger=item.text[:200],
                created_at=datetime.now().isoformat(),
            )
            _save_fact(fact_item, tags=fact_data["tags"])
            log.info(f"Saved fact: {fact_data['fact'][:50]}...")

        # If we finished via do_nothing, no todo action needed
        if done and not decision:
            log.info(f"Completed via do_nothing, {len(facts_to_save)} facts saved")
            return {"created_todos": [], "updated_todos": [], "errors": []}

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
    log.info(f"=== CREATING TODO ===")
    log.info(f"  Title: {task.title}")
    log.info(f"  Description: {task.description}")
    log.info(f"  Tags: {tags}")

    try:
        todo_id = generate_id()
        todo = TodoItem(
            id=todo_id,
            title=task.title,
            description=task.description,
            status="pending",
        )
        save_todo(todo, tags=tags)

        log.info(f"  Created todo ID: {todo_id}")
        log.info(f"=== TODO CREATED ===")

        return {"created_todos": [todo], "updated_todos": [], "errors": []}
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
    log.info(f"=== UPDATING TODO ===")
    log.info(f"  Todo ID: {todo_id}")

    try:
        existing_todo = load_todo(todo_id)

        if not existing_todo:
            log.warning(f"  Todo not found: {todo_id}")
            return {
                "created_todos": [],
                "updated_todos": [],
                "errors": [f"Todo {todo_id} not found"],
            }

        log.info(f"  Existing title: {existing_todo.title}")
        log.info(f"  Existing status: {existing_todo.status}")

        # Build updated fields
        updated_data = existing_todo.model_dump()

        if title is not None:
            log.info(f"  Updating title: {existing_todo.title} -> {title}")
            updated_data["title"] = title

        if description is not None:
            log.info(f"  Updating description: {existing_todo.description} -> {description}")
            updated_data["description"] = description

        if status is not None:
            log.info(f"  Updating status: {existing_todo.status} -> {status}")
            updated_data["status"] = status

        if tags:
            log.info(f"  Tags: {tags}")

        updated_todo = TodoItem.model_validate(updated_data)
        saved_todo = save_todo(updated_todo, tags=tags)

        log.info(f"=== TODO UPDATED ===")

        return {"created_todos": [], "updated_todos": [saved_todo], "errors": []}
    except Exception as e:
        log.error(f"Failed to update todo {todo_id}: {e}")
        return {
            "created_todos": [],
            "updated_todos": [],
            "errors": [f"Failed to update todo {todo_id}: {str(e)}"],
        }
