from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command, Send
from pydantic import BaseModel, Field

from ..config import get_llm
from ..logging_config import AgentLog, get_logger
from ..state import PipelineState, TriagePayload

log = get_logger("document_processor_agent")


# --- Tool Definitions ---


@tool
def do_nothing(reason: str) -> str:
    """Use when the trigger is a pure greeting, thanks, or acknowledgment with no useful information.

    Args:
        reason: Brief explanation of why no action is needed
    """
    return f"Acknowledged: {reason}"


class TriageItem(BaseModel):
    """A single item to triage."""

    text: str = Field(description="The item text to triage")
    context: str = Field(
        default="",
        description="Relevant background context from the document that relates to this item",
    )


class trigger_triage(BaseModel):
    """Input for triggering triage on mentioned items."""

    items: list[TriageItem] = Field(
        description="List of items to triage"
    )


DOCUMENT_PROCESSOR_PROMPT = """You are a context processor that analyzes user input and decides what actions to take.

You will receive:
1. TRIGGER TEXT - the user's recent input
2. DOCUMENT CONTEXT (optional) - background information including recently mentioned items

You have TWO tools available:

1. **do_nothing** - Use for inputs with NO meaningful content:
   - Pure greetings/thanks: "Hello!", "Thanks!", "Hi there", "Got it"
   - Gibberish or meaningless text: single characters, random letters, typos
   - Incomplete fragments that don't convey information
   - Examples: "W", "asdf", "k", "hmm", "..."

2. **trigger_triage** - Use for MEANINGFUL content:
   - Actionable items ("I need to buy groceries", "We need to buy billboards")
   - Status updates ("finished the report")
   - Information that might relate to tasks ("The billboard budget is $5000")
   - Facts about the user ("I'm a software engineer")
   - Context/background info ("Our brand color is blue")

CRITICAL - Recognizing Related Items:
When the trigger text elaborates on something in the document context, extract it as ONE item with context:

Example:
- Document context: "we should focus on setting up a waitlist for felix"
- Trigger: "could be a 2 week sprint, need to discuss with sabesh"
- CORRECT: One item: text="2 week sprint, discuss with sabesh", context="setting up a waitlist for felix"
- WRONG: Two separate items without context

The triage agent will use the context to decide whether to update an existing todo or create a new one.

DECISION RULE:
- If the trigger text is meaningful → trigger_triage
- If the trigger text is meaningless (greetings, gibberish, fragments) → do_nothing
- A single character or very short unclear text is NEVER meaningful

IMPORTANT:
- Extract items ONLY from TRIGGER TEXT, not from document context
- Include relevant context from the document when the trigger elaborates on something
- Do NOT invent or expand on what the user said"""


def document_processor_agent(state: PipelineState) -> Command:
    """Extract context and identify items for triage using tool-based approach."""
    log.info(f"Processing document: {state['document_id']}")
    AgentLog.section("Document Processor")

    trigger_text = state["trigger"]
    log.debug(f"Trigger text length: {len(trigger_text)} chars")

    if not trigger_text.strip():
        log.warning("Trigger text is empty")
        AgentLog.error("doc_processor", "Trigger text is empty")
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
    tools = [do_nothing, trigger_triage]
    llm = get_llm().bind_tools(tools)

    messages: list = [
        SystemMessage(content=DOCUMENT_PROCESSOR_PROMPT),
        HumanMessage(content=human_content),
    ]

    # Collect items for triage
    triage_items: list[TriagePayload] = []

    max_iterations = 5
    for iteration in range(max_iterations):
        log.info(f"LLM iteration {iteration + 1}")

        try:
            response = llm.invoke(messages)
            response = AIMessage(content=response.content, tool_calls=response.tool_calls)
        except Exception as e:
            log.error(f"LLM error: {e}")
            AgentLog.error("doc_processor", f"LLM error: {e}")
            return Command(
                goto=[Send("finalize", {"errors": [f"Document processor error: {str(e)}"]})]
            )

        # Check if there are tool calls
        if not response.tool_calls:
            log.info("No tool calls, finishing")
            AgentLog.action("doc_processor", "LLM returned no tool calls")
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
                AgentLog.decision("doc_processor", "do_nothing", reason)
                messages.append(
                    ToolMessage(content=f"Acknowledged: {reason}", tool_call_id=tool_id)
                )

            elif tool_name == "trigger_triage":
                items = tool_args.get("items", [])
                log.info(f"trigger_triage called with {len(items)} items")
                AgentLog.action("doc_processor", f"Extracted {len(items)} items for triage")

                for item_data in items:
                    item = TriagePayload(
                        text=item_data.get("text", ""),
                        context=item_data.get("context", ""),
                    )
                    triage_items.append(item)
                    log.info(f"Triage item: text='{item.text}' context='{item.context}'")
                    context_str = f"Context: {item.context}" if item.context else "No context"
                    AgentLog.action("doc_processor", f"  - {item.text}", context_str)

                messages.append(
                    ToolMessage(
                        content=f"Queued {len(items)} items for triage",
                        tool_call_id=tool_id,
                    )
                )

            else:
                log.warning(f"Unknown tool: {tool_name}")
                AgentLog.error("doc_processor", f"Unknown tool called: {tool_name}")
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
        AgentLog.action("doc_processor", "No actionable items extracted, skipping triage")
        return Command(goto=[Send("finalize", {})])

    # Fan out to triage agents
    triage_payloads = []
    for item in triage_items:
        triage_payloads.append(Send("triage_agent", item.model_dump()))

    log.info(f"Dispatching {len(triage_payloads)} triage payloads")
    return Command(goto=triage_payloads)
