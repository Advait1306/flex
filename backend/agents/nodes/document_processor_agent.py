import uuid
from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command, Send
from pydantic import BaseModel, Field

from ..config import get_llm
from ..logging_config import get_logger
from ..qdrant_store import save_fact
from ..state import FactItem, MentionedItem, PipelineState, TriagePayload

log = get_logger("document_processor_agent")


# --- Tool Definitions ---


@tool
def do_nothing(reason: str) -> str:
    """Use when the trigger is general/informational and requires no action.

    Args:
        reason: Brief explanation of why no action is needed
    """
    return f"Acknowledged: {reason}"


@tool
def add_fact(
    fact: str,
    category: Literal["preference", "personal", "work", "context", "other"],
    tags: list[str],
) -> str:
    """Use when you learn something about the user worth remembering.

    Args:
        fact: The fact to remember about the user
        category: Category of the fact (preference, personal, work, context, other)
        tags: Keywords for semantic search (e.g., ["preference", "programming", "typescript"])
    """
    return f"Fact recorded: {fact}"


class TriggerTriageInput(BaseModel):
    """Input for triggering triage on mentioned items."""

    items: list[MentionedItem] = Field(
        description="List of actionable items mentioned by the user"
    )


DOCUMENT_PROCESSOR_PROMPT = """You are a context processor that analyzes user input and decides what actions to take.

You will receive:
1. TRIGGER TEXT - the user's recent input
2. DOCUMENT CONTEXT (optional) - background information

You have THREE tools available:

1. **do_nothing** - Use for general/informational messages that need no action
   - Greetings, thanks, acknowledgments
   - Questions that don't imply tasks
   - Pure conversation with no useful information to store

2. **add_fact** - Use ONLY for NON-ACTIONABLE information worth remembering
   Facts are background context, NOT tasks. Never use add_fact for something that should be a todo.

   Categories:
   - "preference": User preferences, styles, likes/dislikes
   - "personal": Personal info about the user
   - "work": Work-related context, projects, team info
   - "context": General knowledge, guidelines, rules, ideas, options, resources
   - "other": Anything else worth remembering

   Examples of FACTS (non-actionable):
   - "I prefer morning meetings" → fact (preference, not a task)
   - "Our brand uses blue as primary color" → fact (guideline)
   - "Hackathons are good team activities" → fact (idea/option for future reference)
   - "The design system is in Figma" → fact (resource location)

   Examples of NOT facts (these are tasks, use trigger_triage):
   - "We need to buy billboards" → task, NOT a fact
   - "I need to fix the login bug" → task, NOT a fact
   - "Let's plan a team event" → task, NOT a fact

3. **trigger_triage** - Use for ACTIONABLE items that should become tasks
   - Things to do ("I need to buy groceries", "We need to buy billboards")
   - Status updates ("finished the report")
   - Each item needs: text, intent, optional status_hint, keywords

INTENT CLASSIFICATION for trigger_triage:
- "create": User wants to add something new (e.g., "I need to buy groceries")
- "update_status": User indicates progress or completion (e.g., "finished the report")
- "add_detail": User provides more info about something (e.g., "the meeting is at 3pm")
- "general": Informational, no clear action needed

STATUS HINTS (for update_status intent):
- "completed": done, finished, completed, shipped, resolved, fixed
- "in_progress": working on, started, began, interviewing, looking into
- "pending": need to, should, want to, planning to

CRITICAL RULES:
- A piece of information is EITHER a fact OR a task, NEVER BOTH
- If it's actionable (something to do), use trigger_triage ONLY
- If it's context/background (not something to do), use add_fact ONLY
- "I'm a software engineer" → add_fact (context about the user)
- "I need to fix the bug" → trigger_triage (actionable task)
- "We need to buy X" → trigger_triage (actionable task, NOT a fact)

You can call MULTIPLE tools when the trigger contains DIFFERENT types of information:
- "I'm a software engineer and I need to fix the login bug" → add_fact (engineer) + trigger_triage (bug fix)
- "We could do hackathons as team events" → add_fact only (idea, not actionable yet)
- "Let's plan a team event for Friday" → trigger_triage only (actionable task)

IMPORTANT:
- Extract items ONLY from TRIGGER TEXT, not from document context
- Do NOT invent or expand on what the user said
- Each distinct actionable item should be separate in trigger_triage
- NEVER call add_fact for something that is actionable"""


def document_processor_agent(state: PipelineState) -> Command:
    """Extract context and identify items for triage using tool-based approach."""
    log.info(f"Processing document: {state['document_id']}")

    trigger_text = state["trigger"]
    log.debug(f"Trigger text length: {len(trigger_text)} chars")

    if not trigger_text.strip():
        log.warning("Trigger text is empty")
        return Command(goto="finalize", update={"errors": ["Trigger text is empty"]})

    # Get pre-extracted document context
    doc_context = state.get("document_context", "")
    if doc_context:
        log.debug(f"Document context length: {len(doc_context)} chars")

    # Build the human message
    human_content = f"TRIGGER TEXT (extract items from this):\n{trigger_text}"
    if doc_context:
        human_content += f"\n\nDOCUMENT CONTEXT (background only, do not extract items):\n{doc_context}"

    # Bind tools to LLM
    tools = [do_nothing, add_fact, TriggerTriageInput]
    llm = get_llm().bind_tools(tools)

    messages: list = [
        SystemMessage(content=DOCUMENT_PROCESSOR_PROMPT),
        HumanMessage(content=human_content),
    ]

    # Collect items for triage
    triage_items: list[MentionedItem] = []
    facts_saved: list[str] = []

    max_iterations = 5
    for iteration in range(max_iterations):
        log.info(f"LLM iteration {iteration + 1}")

        try:
            response = llm.invoke(messages)
            response = AIMessage(content=response.content, tool_calls=response.tool_calls)
        except Exception as e:
            log.error(f"LLM error: {e}")
            return Command(
                goto=[Send("finalize", {"errors": [f"Document processor error: {str(e)}"]})]
            )

        # Check if there are tool calls
        if not response.tool_calls:
            log.info("No tool calls, finishing")
            break

        messages.append(response)

        # Process each tool call
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            log.info(f"Processing tool call: {tool_name}")

            if tool_name == "do_nothing":
                reason = tool_args.get("reason", "No reason provided")
                log.info(f"do_nothing called: {reason}")
                messages.append(
                    ToolMessage(content=f"Acknowledged: {reason}", tool_call_id=tool_id)
                )

            elif tool_name == "add_fact":
                fact_text = tool_args.get("fact", "")
                category = tool_args.get("category", "other")
                tags = tool_args.get("tags", [])

                log.info(f"add_fact called: {fact_text[:50]}... category={category} tags={tags}")

                # Save fact to Qdrant
                fact_item = FactItem(
                    id=str(uuid.uuid4()),
                    fact=fact_text,
                    category=category,
                    tags=tags,
                    source_trigger=trigger_text[:200],
                    created_at=datetime.now().isoformat(),
                )
                save_fact(fact_item, tags=tags)
                facts_saved.append(fact_text)

                messages.append(
                    ToolMessage(content=f"Fact saved: {fact_text}", tool_call_id=tool_id)
                )

            elif tool_name == "TriggerTriageInput":
                items = tool_args.get("items", [])
                log.info(f"trigger_triage called with {len(items)} items")

                for item_data in items:
                    item = MentionedItem(
                        text=item_data.get("text", ""),
                        intent=item_data.get("intent", "general"),
                        status_hint=item_data.get("status_hint"),
                        related_keywords=item_data.get("related_keywords", []),
                        background_info=item_data.get("background_info"),
                    )
                    triage_items.append(item)
                    log.info(
                        f"Triage item: text='{item.text}' intent={item.intent} "
                        f"status_hint={item.status_hint} keywords={item.related_keywords}"
                    )

                messages.append(
                    ToolMessage(
                        content=f"Queued {len(items)} items for triage",
                        tool_call_id=tool_id,
                    )
                )

            else:
                log.warning(f"Unknown tool: {tool_name}")
                messages.append(
                    ToolMessage(content=f"Unknown tool: {tool_name}", tool_call_id=tool_id)
                )

        # Check if we should continue (if LLM wants to make more calls)
        # For now, we break after processing all calls in one turn
        break

    # Log summary
    log.info(f"Document processor complete: {len(facts_saved)} facts saved, {len(triage_items)} items for triage")

    # Route to triage or finalize
    if not triage_items:
        log.info("No actionable items, going to finalize")
        return Command(goto=[Send("finalize", {})])

    # Fan out to triage agents
    triage_payloads = []
    for item in triage_items:
        payload: TriagePayload = {"item": item}
        triage_payloads.append(Send("triage_agent", payload))

    log.info(f"Dispatching {len(triage_payloads)} triage payloads")
    return Command(goto=triage_payloads)
