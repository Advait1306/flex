import asyncio
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable
from pydantic import BaseModel, Field

from ..config import get_llm
from logging_config import AgentLog, get_logger
from models import TriagePayload
from .triage_agent import triage_agent

log = get_logger("daemon_processor_agent")


class DaemonExtractionResult(BaseModel):
    """Result of analyzing an app snapshot."""

    action: Literal["do_nothing", "triage"] = Field(
        description="do_nothing when the snapshot has no meaningful signal, triage when actionable items are found"
    )
    items: list[TriagePayload] = Field(
        default_factory=list,
        description="Items to triage. Only populated when action is 'triage'.",
    )


DAEMON_PROCESSOR_PROMPT = """You are a context processor that analyzes app content snapshots captured from the user's screen via accessibility APIs.

You will receive a raw accessibility tree snapshot from an app. Your job is to find meaningful signal — tasks, decisions, important information, status updates — and filter out UI noise.

UNDERSTANDING ACCESSIBILITY TREE FORMAT:
- Markers like [Button], [Link], [Heading], [Cell] are accessibility role annotations — they describe what a UI element IS, not what the user wants to DO
- Button and link labels are navigation affordances (e.g. "Go back", "Submit comment", "Skip to content"), NOT tasks or actions the user intends to take
- Never treat the text inside an AX role marker as user intent

IDENTIFYING THE SUBJECT:
- The **subject** is the primary entity the user is actively viewing — an issue, PR, document, thread, etc.
- Usually found in the page title, focused tab, or main content heading (often the first line of the snapshot)
- Every extracted item MUST set `context` to identify the subject (e.g. "ASEE-15 feat: automatic testing for UI")
- If the user is viewing a list/board of work items (issues, tasks, PRs), each listed item IS signal — extract them as triage items with the list view as context
- If you cannot identify a clear subject AND there are no listed work items, the snapshot is likely just navigation/chrome — use do_nothing

FILTER OUT (UI chrome / noise):
- Navigation elements, menus, toolbars, buttons, tab labels
- Timestamps, read receipts, online/offline indicators
- Generic UI text ("Type a message", "Search", "Settings")
- Repeated structural elements (sidebar items, header/footer)
- Empty or purely decorative elements
- Linked resources: issues, PRs, comments, and other entities referenced as links or in activity feeds are contextual references, NOT separate actionable items
- Only extract items from the **primary content area**, not from sidebar navigation, activity logs, or linked resource lists

EXTRACT (signal):
- Action items or tasks mentioned in conversations or content
- Decisions made or pending ("let's go with option B", "need to decide on...")
- Important information or updates ("the deadline moved to Friday", "budget approved for $5k")
- Status updates on projects or work ("deployed v2.1", "PR merged")
- Commitments or promises ("I'll send that over tomorrow")

GROUPING:
- Group triage items by the subject being acted on — a single triage item per subject can include multiple actions/signals about that subject
- Fewer, higher-quality items is always better

IMPORTANT:
- Err on fewer, higher-quality items. Only extract things genuinely worth tracking.
- Do NOT extract trivial conversation (greetings, small talk, acknowledgments)
- Do NOT invent or expand on what's in the content
- Preserve the user's intent — keep action verbs and phrasing
- Each item's text should stand on its own without needing the full snapshot for context"""


@traceable(name="daemon_extract_triage_items", run_type="chain")
def _extract_triage_items_from_snapshot(
    content: str, app_name: str, app_category: str
) -> list[TriagePayload]:
    """Use structured output to extract triage items from an app snapshot.

    Content is sent to the LLM without truncation. If the content exceeds the
    model's context window, the LLM call will fail and we'll log the error.
    This is intentional — we'd rather skip an oversized snapshot than silently
    lose signal by truncating.
    """
    if not content.strip():
        log.warning("Snapshot content is empty")
        AgentLog.error("daemon_processor", "Snapshot content is empty")
        return []

    human_content = (
        f"App: {app_name} ({app_category})\n\n"
        f"SNAPSHOT CONTENT:\n{content}"
    )

    messages = [
        SystemMessage(content=DAEMON_PROCESSOR_PROMPT),
        HumanMessage(content=human_content),
    ]

    try:
        llm = get_llm().with_structured_output(DaemonExtractionResult)
        result = llm.invoke(messages)
    except Exception as e:
        log.error(f"LLM error: {e}")
        AgentLog.error("daemon_processor", f"LLM error: {e}")
        return []

    if result.action == "do_nothing":
        log.info("LLM chose do_nothing — no signal in snapshot")
        AgentLog.decision("daemon_processor", "do_nothing", "No meaningful content in snapshot")
        return []

    log.info(f"LLM extracted {len(result.items)} items for triage")
    AgentLog.action("daemon_processor", f"Extracted {len(result.items)} items for triage")

    return result.items


@traceable(name="daemon_processor", run_type="chain")
async def run_daemon_processor_agent(
    content: str,
    app_name: str,
    bundle_id: str,
    app_category: str,
    content_hash: str,
    *,
    user_id: int,
) -> None:
    """Entry point: extract items from app snapshot, fan out to triage agents."""
    log.info(f"Starting daemon processor for {app_name} ({bundle_id}), hash={content_hash}")

    agent_log_file = AgentLog.start()
    log.info(f"Agent log: {agent_log_file}")

    AgentLog.section(f"Daemon Processor - {app_name} ({bundle_id})")
    AgentLog.action(
        "daemon_processor",
        "Snapshot received",
        f"App: {app_name}, Category: {app_category}, Hash: {content_hash}, Content length: {len(content)} chars",
    )

    try:
        AgentLog.section("Daemon Processor")
        log.info(f"Processing snapshot: {len(content)} chars")

        triage_items = _extract_triage_items_from_snapshot(content, app_name, app_category)

        if not triage_items:
            log.info("No actionable items, finishing")
            AgentLog.action("daemon_processor", "No actionable items extracted, skipping triage")
            return

        log.info(f"Dispatching {len(triage_items)} items to triage agents")
        await asyncio.gather(
            *[asyncio.to_thread(triage_agent, item, user_id=user_id) for item in triage_items]
        )

        log.info("Daemon processor complete")
        AgentLog.section("Pipeline Complete")

    except Exception as e:
        log.error(f"Daemon processor error: {e}")
        AgentLog.error("daemon_processor", f"Daemon processor error: {e}")
        raise

    finally:
        AgentLog.close()
