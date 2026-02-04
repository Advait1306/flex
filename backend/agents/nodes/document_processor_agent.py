from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command, Send
from pydantic import BaseModel, Field

from ..config import get_llm
from ..logging_config import AgentLog, get_logger
from ..state import MentionedItem, PipelineState, TriagePayload

log = get_logger("document_processor_agent")


# --- Tool Definitions ---


@tool
def do_nothing(reason: str) -> str:
    """Use when the trigger is a pure greeting, thanks, or acknowledgment with no useful information.

    Args:
        reason: Brief explanation of why no action is needed
    """
    return f"Acknowledged: {reason}"


class TriggerTriageInput(BaseModel):
    """Input for triggering triage on mentioned items."""

    items: list[MentionedItem] = Field(
        description="List of actionable items mentioned by the user"
    )


DOCUMENT_PROCESSOR_PROMPT = """You are a context processor that analyzes user input and decides what actions to take.

You will receive:
1. TRIGGER TEXT - the user's recent input
2. DOCUMENT CONTEXT (optional) - background information

You have TWO tools available:

1. **do_nothing** - Use for inputs with NO meaningful content:
   - Pure greetings/thanks: "Hello!", "Thanks!", "Hi there", "Got it"
   - Gibberish or meaningless text: single characters, random letters, typos
   - Incomplete fragments that don't convey information
   - Examples: "W", "asdf", "k", "hmm", "..."

2. **trigger_triage** - Use ONLY for MEANINGFUL content:
   - Actionable items ("I need to buy groceries", "We need to buy billboards")
   - Status updates ("finished the report")
   - Information that might relate to tasks ("The billboard budget is $5000")
   - Facts about the user ("I'm a software engineer")
   - Context/background info ("Our brand color is blue")

   The triage agent can search existing todos and decide whether to:
   - Create a new todo
   - Update an existing todo with this information
   - Save it as a fact for future reference
   - Ignore it

INTENT CLASSIFICATION for trigger_triage:
- "create": User wants to add something new (e.g., "I need to buy groceries")
- "update_status": User indicates progress or completion (e.g., "finished the report")
- "add_detail": User provides more info about something (e.g., "the budget is $5000")
- "general": Informational, context, or facts about the user

STATUS HINTS (for update_status intent):
- "completed": done, finished, completed, shipped, resolved, fixed
- "in_progress": working on, started, began, interviewing, looking into
- "pending": need to, should, want to, planning to

DECISION RULE:
- If the trigger text is meaningful (conveys actual information) → trigger_triage
- If the trigger text is meaningless (greetings, gibberish, fragments) → do_nothing
- A single character or very short unclear text is NEVER meaningful

IMPORTANT:
- Extract items ONLY from TRIGGER TEXT, not from document context
- Do NOT invent or expand on what the user said
- Each distinct item should be separate in trigger_triage"""


def document_processor_agent(state: PipelineState) -> Command:
    """Extract context and identify items for triage using tool-based approach."""
    log.info(f"Processing document: {state['document_id']}")
    AgentLog.section("Document Processor")

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
    tools = [do_nothing, TriggerTriageInput]
    llm = get_llm().bind_tools(tools)

    messages: list = [
        SystemMessage(content=DOCUMENT_PROCESSOR_PROMPT),
        HumanMessage(content=human_content),
    ]

    # Collect items for triage
    triage_items: list[MentionedItem] = []

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

            elif tool_name == "TriggerTriageInput":
                items = tool_args.get("items", [])
                log.info(f"trigger_triage called with {len(items)} items")
                AgentLog.action("doc_processor", f"Extracted {len(items)} items for triage")

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
                    AgentLog.action("doc_processor", f"  - {item.text}", f"Intent: {item.intent}")

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
    log.info(f"Document processor complete: {len(triage_items)} items for triage")

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
