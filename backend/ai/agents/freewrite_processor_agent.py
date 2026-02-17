import asyncio
import uuid
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable
from pydantic import BaseModel, Field

from ..config import get_llm
from logging_config import AgentLog, get_logger
from models import TriagePayload
from .triage_agent import triage_agent

log = get_logger("freewrite_processor_agent")


class ExtractionResult(BaseModel):
    """Result of analyzing trigger text."""

    action: Literal["do_nothing", "triage"] = Field(
        description="do_nothing for meaningless input (greetings, gibberish), triage for meaningful content"
    )
    items: list[TriagePayload] = Field(
        default_factory=list,
        description="Items to triage. Only populated when action is 'triage'.",
    )


FREEWRITE_PROCESSOR_PROMPT = """You are a context processor that analyzes user input and extracts actionable items.

You will receive:
1. TRIGGER TEXT - the user's recent input
2. DOCUMENT CONTEXT (optional) - background information including recently mentioned items

Set action to "do_nothing" for inputs with NO meaningful content:
- Pure greetings/thanks: "Hello!", "Thanks!", "Hi there", "Got it"
- Gibberish or meaningless text: single characters, random letters, typos
- Incomplete fragments that don't convey information
- A single character or very short unclear text is NEVER meaningful

Set action to "triage" and populate items for MEANINGFUL content:
- Actionable items ("I need to buy groceries", "We need to buy billboards")
- Status updates ("finished the report")
- Information that might relate to tasks ("The billboard budget is $5000")
- Facts about the user ("I'm a software engineer")
- Context/background info ("Our brand color is blue")

IDENTIFYING SUBJECTS:
- A **subject** is a distinct entity the user mentions — a task, issue, PR, project, person, etc.
- When the trigger text mentions MULTIPLE subjects, extract a SEPARATE item for each subject
- Every extracted item MUST set `context` to identify what it relates to — the subject, any relationships, or relevant document context
- If the trigger text elaborates on something in the document context, set `context` to link back to that subject

Example — multiple subjects with a relationship:
- Trigger: "need to update the onboarding flow, but first fix the billing page since it depends on that"
- CORRECT: Two items:
  - text="need to update the onboarding flow", context="depends on billing page fix"
  - text="fix the billing page", context="blocking onboarding flow update"
- WRONG: One combined item that loses a subject

Example — trigger elaborates on document context:
- Document context: "we should focus on setting up a waitlist for felix"
- Trigger: "could be a 2 week sprint, need to discuss with sabesh"
- CORRECT: One item: text="2 week sprint, discuss with sabesh", context="setting up a waitlist for felix"
- WRONG: Two separate items without context

GROUPING:
- Group by subject — one triage item per subject, combining multiple signals about the same subject
- Fewer, higher-quality items is always better — but do NOT collapse distinct subjects into a single item

IMPORTANT:
- Extract items ONLY from TRIGGER TEXT, not from document context
- Include relevant context from the document when the trigger elaborates on something
- Do NOT invent or expand on what the user said
- Preserve the user's intent in the item text — keep action verbs and intent phrases like "need to", "should", "want to", etc. Do NOT reduce items to bare noun phrases that lose the original meaning.
  - CORRECT: "need to get pricing page updated before launch"
  - WRONG: "pricing page updated before launch" (reads as a completed statement, not a task)"""


@traceable(name="extract_triage_items", run_type="chain")
def _extract_triage_items(
    trigger_text: str, document_context: str
) -> list[TriagePayload]:
    """Use structured output to extract triage items from trigger text."""
    if not trigger_text.strip():
        log.warning("Trigger text is empty")
        AgentLog.error("freewrite_processor", "Trigger text is empty")
        return []

    if document_context:
        log.debug(f"Document context length: {len(document_context)} chars")

    human_content = f"TRIGGER TEXT (extract items from this):\n{trigger_text}"
    if document_context:
        human_content += f"\n\nDOCUMENT CONTEXT (background only):\n{document_context}"

    messages = [
        SystemMessage(content=FREEWRITE_PROCESSOR_PROMPT),
        HumanMessage(content=human_content),
    ]

    try:
        llm = get_llm().with_structured_output(ExtractionResult)
        result = llm.invoke(messages)
    except Exception as e:
        log.error(f"LLM error: {e}")
        AgentLog.error("freewrite_processor", f"LLM error: {e}")
        return []

    if result.action == "do_nothing":
        log.info("LLM chose do_nothing")
        AgentLog.decision("freewrite_processor", "do_nothing", "No meaningful content")
        return []

    log.info(f"LLM extracted {len(result.items)} items for triage")
    AgentLog.action("freewrite_processor", f"Extracted {len(result.items)} items for triage")

    return result.items


@traceable(name="freewrite_processor", run_type="chain")
async def run_freewrite_processor_agent(
    trigger: str, document_id: str | None = None, document_context: str = "", *, user_id: int
) -> None:
    """Entry point: extract items from trigger text, fan out to triage agents."""
    doc_id = document_id or f"cli-{uuid.uuid4().hex[:8]}"
    log.info(f"Starting freewrite processor for document: {doc_id}")

    # Start the agent log
    agent_log_file = AgentLog.start()
    log.info(f"Agent log: {agent_log_file}")

    AgentLog.section(f"Freewrite Processor - Document: {doc_id}")
    AgentLog.action("freewrite_processor", "Input received", f"Trigger: {trigger[:200]}{'...' if len(trigger) > 200 else ''}")
    if document_context:
        AgentLog.action("freewrite_processor", "Document context", document_context)

    try:
        AgentLog.section("Freewrite Processor")
        log.info(f"Processing trigger: {len(trigger)} chars")

        triage_items = _extract_triage_items(trigger, document_context)

        if not triage_items:
            log.info("No actionable items, finishing")
            AgentLog.action("freewrite_processor", "No actionable items extracted, skipping triage")
            return

        # Fan out to triage agents
        log.info(f"Dispatching {len(triage_items)} items to triage agents")
        await asyncio.gather(
            *[asyncio.to_thread(triage_agent, item, user_id=user_id) for item in triage_items]
        )

        log.info("Freewrite processor complete")
        AgentLog.section("Pipeline Complete")

    except Exception as e:
        log.error(f"Freewrite processor error: {e}")
        AgentLog.error("freewrite_processor", f"Freewrite processor error: {e}")
        raise

    finally:
        AgentLog.close()
