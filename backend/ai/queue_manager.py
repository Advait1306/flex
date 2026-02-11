import asyncio
from dataclasses import dataclass
from typing import Literal

from .agents.freewrite_processor_agent import run_freewrite_processor_agent
from .agents.daemon_processor_agent import run_daemon_processor_agent
from logging_config import get_logger

log = get_logger("queue_manager")


@dataclass
class PipelineTrigger:
    """A queued pipeline trigger."""

    trigger_type: Literal["freewrite", "daemon"]
    user_id: int

    # Freewrite fields
    trigger: str = ""
    document_id: str = ""
    document_context: str = ""

    # Daemon fields
    app_name: str = ""
    bundle_id: str = ""
    app_category: str = ""
    content: str = ""
    content_hash: str = ""


class PipelineQueueManager:
    """Manages a queue of pipeline triggers, processing one at a time."""

    def __init__(self):
        self._queue: asyncio.Queue[PipelineTrigger] = asyncio.Queue()
        self._is_processing = False
        self._current_task: asyncio.Task | None = None

    async def enqueue(
        self,
        trigger: str,
        document_id: str,
        user_id: int,
        document_context: str = "",
    ) -> None:
        """Add a freewrite trigger to the queue."""
        item = PipelineTrigger(
            trigger_type="freewrite",
            trigger=trigger,
            document_id=document_id,
            user_id=user_id,
            document_context=document_context,
        )
        await self._queue.put(item)
        log.info(f"Queued freewrite trigger for document {document_id}: {trigger[:50]}...")
        log.info(f"Queue size: {self._queue.qsize()}")

        if not self._is_processing:
            self._current_task = asyncio.create_task(self._process_queue())

    async def enqueue_daemon(
        self,
        app_name: str,
        bundle_id: str,
        app_category: str,
        content: str,
        content_hash: str,
        user_id: int,
    ) -> None:
        """Add a daemon snapshot trigger to the queue."""
        item = PipelineTrigger(
            trigger_type="daemon",
            user_id=user_id,
            app_name=app_name,
            bundle_id=bundle_id,
            app_category=app_category,
            content=content,
            content_hash=content_hash,
        )
        await self._queue.put(item)
        log.info(f"Queued daemon trigger for {app_name} ({bundle_id}), hash={content_hash}")
        log.info(f"Queue size: {self._queue.qsize()}")

        if not self._is_processing:
            self._current_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Process triggers from the queue one at a time."""
        self._is_processing = True
        log.info("Queue processor started")

        try:
            while not self._queue.empty():
                item = await self._queue.get()

                try:
                    if item.trigger_type == "freewrite":
                        log.info(f"Processing freewrite trigger for document {item.document_id}")
                        await run_freewrite_processor_agent(
                            trigger=item.trigger,
                            document_context=item.document_context,
                            document_id=item.document_id,
                            user_id=item.user_id,
                        )
                        log.info(f"Pipeline complete for {item.document_id}")
                    elif item.trigger_type == "daemon":
                        log.info(f"Processing daemon trigger for {item.app_name} ({item.bundle_id})")
                        await run_daemon_processor_agent(
                            content=item.content,
                            app_name=item.app_name,
                            bundle_id=item.bundle_id,
                            app_category=item.app_category,
                            content_hash=item.content_hash,
                            user_id=item.user_id,
                        )
                        log.info(f"Pipeline complete for {item.app_name} ({item.bundle_id})")
                except Exception as e:
                    log.error(f"Pipeline error for {item.trigger_type}: {e}")
                finally:
                    self._queue.task_done()

        finally:
            self._is_processing = False
            log.info("Queue processor stopped")

    def get_status(self) -> dict:
        """Get current queue status."""
        return {
            "queue_size": self._queue.qsize(),
            "is_processing": self._is_processing,
        }


# Global singleton
_queue_manager: PipelineQueueManager | None = None


def get_queue_manager() -> PipelineQueueManager:
    """Get the global queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = PipelineQueueManager()
    return _queue_manager
