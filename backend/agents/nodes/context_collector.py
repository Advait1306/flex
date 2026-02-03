from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command, Send
from pydantic import BaseModel, Field

from ..config import get_llm
from ..logging_config import get_logger
from ..state import MentionedItem, PipelineState, TriagePayload

log = get_logger("context_collector")


class ContextCollectorResult(BaseModel):
    """Result of extracting context from user input."""

    mentioned_items: list[MentionedItem] = Field(
        default_factory=list,
        description="Items explicitly mentioned by the user, each with its own relevant background context",
    )


CONTEXT_COLLECTOR_PROMPT = """You are a context extractor that identifies actionable items from the TRIGGER TEXT only.

You will receive:
1. TRIGGER TEXT - the user's recent input (extract items ONLY from this)
2. DOCUMENT CONTEXT (optional) - background information to help understand references (do NOT extract items from this)

Your job is to:
1. Extract items ONLY from the TRIGGER TEXT
2. Classify each item's intent
3. Extract relevant keywords for matching to existing tasks
4. For each item, include relevant background_info from the document context (if applicable to that specific item)

IMPORTANT RULES:
- ONLY extract items from the TRIGGER TEXT, never from the document context
- The document is just background - do not create tasks from it
- Do NOT invent, decompose, or expand on what the user said
- Each distinct thing mentioned in the trigger should be a separate item
- Each item should have its own background_info with context relevant to THAT item only

INTENT CLASSIFICATION:
- "create": User wants to add something new (e.g., "I need to buy groceries")
- "update_status": User indicates progress or completion (e.g., "finished the report", "started working on X")
- "add_detail": User provides more info about something (e.g., "the meeting is at 3pm")
- "general": Informational, no clear action needed

STATUS HINTS (for update_status intent):
- "completed": done, finished, completed, shipped, resolved, fixed, looks good
- "in_progress": working on, started, began, interviewing, looking into, researching
- "pending": need to, should, want to, planning to

EXAMPLES:

Trigger: "Need to buy groceries and pick up laundry"
→ Two items: "buy groceries" (create) and "pick up laundry" (create)

Trigger: "Finished the design review"
→ One item: "design review" (update_status, completed), keywords: ["design", "review"]

Trigger: "Started interviewing candidates for the designer role"
Document mentions: "We're hiring a senior designer for the mobile team"
→ One item: "interviewing candidates for designer" (update_status, in_progress), keywords: ["interview", "designer", "hire"], background_info: "Hiring senior designer for mobile team" """


def extract_text_from_blocks(blocks: list[dict]) -> str:
    """Extract text content from BlockNote blocks."""
    if not blocks:
        return ""
    text_parts = []
    for block in blocks:
        if isinstance(block, dict):
            content = block.get("content", [])
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
    return "\n".join(text_parts)


def context_collector(state: PipelineState) -> Command:
    """Extract context and fan out to triage agents (LLM #1)."""
    log.info(f"Collecting context for document: {state['document_id']}")

    trigger_text = state["trigger"]
    log.debug(f"Trigger text length: {len(trigger_text)} chars")

    if not trigger_text.strip():
        log.warning("Trigger text is empty")
        return Command(goto=[Send("finalize", {"errors": ["Trigger text is empty"]})])

    # Extract document context (optional)
    doc_text = extract_text_from_blocks(state.get("document_content", []))
    if doc_text:
        log.debug(f"Document context length: {len(doc_text)} chars")

    # Build the human message
    human_content = f"TRIGGER TEXT (extract items from this):\n{trigger_text}"
    if doc_text:
        human_content += f"\n\nDOCUMENT CONTEXT (background only, do not extract items):\n{doc_text}"

    llm = get_llm().with_structured_output(ContextCollectorResult, method="function_calling")

    messages = [
        SystemMessage(content=CONTEXT_COLLECTOR_PROMPT),
        HumanMessage(content=human_content),
    ]

    try:
        log.info("Invoking LLM for context extraction")
        result = cast(ContextCollectorResult, llm.invoke(messages))

        log.info(f"Extracted {len(result.mentioned_items)} mentioned items")

        if not result.mentioned_items:
            log.info("No actionable items found")
            return Command(goto=[Send("finalize", {})])

        # Fan out directly to triage agents
        triage_payloads = []
        for item in result.mentioned_items:
            payload: TriagePayload = {"item": item}
            log.info(f"Triage payload: text='{item.text}' intent={item.intent} status_hint={item.status_hint} keywords={item.related_keywords} background='{item.background_info}'")
            triage_payloads.append(Send("triage_agent", payload))

        log.info(f"Dispatching {len(triage_payloads)} triage payloads")
        return Command(goto=triage_payloads)

    except Exception as e:
        log.error(f"Context collector error: {e}")
        return Command(goto=[Send("finalize", {"errors": [f"Context collector error: {str(e)}"]})])
