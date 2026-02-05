import json
import uuid
from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from ..config import get_llm
from ..logging_config import AgentLog, get_logger
from models import FactItem, TriagePayload
from store import (
    FactSearchResult,
    SearchResult,
    create_todo as _create_todo,
    update_todo as _update_todo,
    search_todos as _search_todos,
)
from store.facts import save_fact as _save_fact, search_facts as _search_facts

log = get_logger("triage_agent")


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
    fact_item = FactItem(
        id=str(uuid.uuid4()),
        fact=fact,
        category=category,
        tags=tags,
        created_at=datetime.now().isoformat(),
    )
    _save_fact(fact_item, tags=tags)
    log.info(f"Saved fact: {fact[:50]}...")
    return f"Fact saved: {fact}"


@tool
def create_todo(
    title: str,
    tags: list[str],
    description: str | None = None,
    parent_id: str | None = None,
) -> str:
    """Create a new todo item.

    Args:
        title: Title close to the original item text
        tags: 2-5 searchable tags/topics (e.g., ["groceries", "shopping"])
        description: Optional description with relevant details
        parent_id: ID of existing todo to set as parent if related
    """
    todo = _create_todo(title=title, description=description, parent_id=parent_id, tags=tags)

    details = f"ID: {todo.id}\nTitle: {title}"
    if description:
        details += f"\nDescription: {description}"
    if parent_id:
        details += f"\nParent ID: {parent_id}"
    AgentLog.result("triage", f"Created todo:\n{details}")

    return f"Todo created: {title} (ID: {todo.id})"


@tool
def update_todo(
    todo_id: str,
    tags: list[str],
    title: str | None = None,
    description: str | None = None,
    status: Literal["pending", "in_progress", "completed", "cancelled"] | None = None,
) -> str:
    """Update an existing todo item.

    Args:
        todo_id: ID of the todo to update
        tags: 2-5 searchable tags/topics
        title: New title if it should change
        description: COMPLETE new description (preserve existing + add new)
        status: New status if it should change
    """
    try:
        _update_todo(todo_id, title=title, description=description, status=status, tags=tags)
    except ValueError as e:
        log.warning(str(e))
        return f"Error: {e}"

    changes = []
    if title is not None:
        changes.append(f"Title: {title}")
    if description is not None:
        changes.append(
            f"Description: {description[:100]}{'...' if len(description) > 100 else ''}"
        )
    if status is not None:
        changes.append(f"Status: {status}")
    AgentLog.result(
        "triage",
        f"Updated todo {todo_id}:\n" + "\n".join(changes)
        if changes
        else "No changes",
    )

    return f"Todo updated: {todo_id}"


@tool
def do_nothing(reason: str) -> str:
    """Use when no action is needed - no todo to create/update and no fact worth saving.

    Args:
        reason: Brief explanation of why no action is needed
    """
    return f"No action taken: {reason}"


TRIAGE_AGENT_PROMPT = """You are a triage agent that decides how to handle a SINGLE mentioned item.

You receive ONE item at a time with:
- **text**: The item to triage
- **context** (optional): What this item relates to (e.g., a recently mentioned task)

Your job is to search for related todos/facts and make a decision.

You have access to these tools:
1. **search_todos** - Find existing todos that might be related to the current item
2. **search_facts** - Find known facts/context about the user (preferences, contacts, past decisions)
3. **save_fact** - Save information worth remembering (NOT task-related)
4. **create_todo** - Create a new todo item
5. **update_todo** - Update an existing todo item
6. **do_nothing** - When no action is needed at all

WORKFLOW:
1. If context is provided, search_todos using the context first (it likely refers to an existing todo)
2. Then search_todos using the item text to find other related todos
3. search_facts for relevant preferences or context
4. Make your decision by calling create_todo, update_todo, save_fact, or do_nothing

DECISION LOGIC:

**When context is provided**, the item is likely adding details to an existing todo:
- Search for the todo matching the context
- If found, use update_todo to add the item text to that todo's description
- Example: text="2 week sprint, discuss with sabesh", context="setting up a waitlist for felix"
  → search for "waitlist felix" → update_todo to add the new details

**When NO context is provided**, decide based on the item text:

ACTIONABLE TASK = something that needs to be DONE (verb-based: hire, buy, fix, call, send, etc.)
INFORMATION = context, details, constraints (budget, deadline, requirements)

If item is an ACTIONABLE TASK:
- Use create_todo to create a new todo
- If related to an existing todo, set parent_id to link them

If item is INFORMATION about an existing todo:
- Use update_todo to add the info to that todo's description

If there is NO related todo:
- For actionable items → create_todo
- For valuable context/info → save_fact, then do_nothing
- For pure greetings/thanks → do_nothing only

EXAMPLES:

With context:
- text="2 week sprint, discuss with sabesh", context="setting up a waitlist for felix"
  → search_todos("waitlist felix") → find todo → update_todo(todo_id="<id>", description="<existing> + Timeline: 2 week sprint. Need to discuss with Sabesh.", tags=["waitlist", "felix", "sprint", "sabesh"])

Without context:
- text="Buy groceries"
  → search_todos → create_todo(title="Buy groceries", tags=["groceries", "shopping"])

- text="Hire a designer for the billboard" + existing "Buy billboards" todo
  → search_todos → create_todo(title="Hire a designer for billboard", parent_id="<billboard-todo-id>", tags=["designer", "billboard", "hiring"])

CRITICAL RULES:
- When context is provided, prioritize finding and updating the related todo
- ALWAYS search_todos before making any decision
- Only use update_todo for adding INFORMATION to existing todos, not for new actionable tasks
- Do NOT invent tasks beyond what was explicitly mentioned
- TAGS ARE MANDATORY for every create_todo/update_todo call - always provide 2-5 searchable tags

For create_todo:
- title: Close to the original item text
- description: Include relevant facts found (preferences, contacts, context)
- tags: REQUIRED - 2-5 key searchable concepts (e.g., ["standups", "meetings", "team"])

For update_todo:
- todo_id: The ID of the existing todo to update
- description: Write the COMPLETE new description - preserve ALL existing info and add the new info
- tags: REQUIRED - 2-5 key searchable concepts for this todo
- NEVER remove existing information unless explicitly asked
"""

MAX_TOOL_CALLS = 5


def triage_agent(item: TriagePayload) -> None:
    """Triage a single item using tool-calling to search for existing todos."""
    log.info(f"Triaging item: {item.text}")
    AgentLog.section(f"Triage: {item.text[:50]}{'...' if len(item.text) > 50 else ''}")
    context_info = f"Context: {item.context}" if item.context else "No context"
    AgentLog.action("triage", "Processing item", f"Text: {item.text}\n{context_info}")

    human_content = f"Item to triage: {item.text}"
    if item.context:
        human_content += f"\n\nContext (what this item relates to): {item.context}"

    messages = [
        SystemMessage(content=TRIAGE_AGENT_PROMPT),
        HumanMessage(content=human_content),
    ]

    llm = get_llm()
    tools = [search_todos, search_facts, save_fact, create_todo, update_todo, do_nothing]
    llm_with_tools = llm.bind_tools(tools)

    try:
        for i in range(MAX_TOOL_CALLS):
            log.info(f"Agent loop iteration {i + 1}")

            response: AIMessage = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                log.warning("LLM returned no tool calls, prompting for decision")
                messages.append(
                    HumanMessage(
                        content="Please make your decision using create_todo, update_todo, save_fact, or do_nothing."
                    )
                )
                continue

            for tool_call in response.tool_calls:
                name = tool_call["name"]
                args = tool_call["args"]
                log.info(f"Tool call: {name}({args})")
                AgentLog.tool_call(name, args)

                tool_fn = {t.name: t for t in tools}[name]
                result = tool_fn.invoke(args)

                log.info(f"Tool result for {name}: {result[:200]}")
                AgentLog.tool_result(name, result)

                messages.append(
                    ToolMessage(content=result, tool_call_id=tool_call["id"])
                )

    except Exception as e:
        log.error(f"Triage agent error: {e}")
