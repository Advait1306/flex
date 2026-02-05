import asyncio
from dataclasses import dataclass

from .agents.freewrite_processor_agent import run_freewrite_processor_agent
from .logging_config import get_logger

log = get_logger("queue_manager")


@dataclass
class PipelineTrigger:
    """A queued pipeline trigger."""

    trigger: str
    document_id: str
    document_context: str = ""  # Pre-extracted and truncated document text


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
        document_context: str = "",
    ) -> None:
        """Add a trigger to the queue."""
        item = PipelineTrigger(
            trigger=trigger,
            document_id=document_id,
            document_context=document_context,
        )
        await self._queue.put(item)
        log.info(f"Queued trigger for document {document_id}: {trigger[:50]}...")
        log.info(f"Queue size: {self._queue.qsize()}")

        # Start processing if not already running
        if not self._is_processing:
            self._current_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Process triggers from the queue one at a time."""
        self._is_processing = True
        log.info("Queue processor started")

        try:
            while not self._queue.empty():
                item = await self._queue.get()
                log.info(f"Processing trigger for document {item.document_id}")

                try:
                    await run_freewrite_processor_agent(
                        trigger=item.trigger,
                        document_context=item.document_context,
                        document_id=item.document_id,
                    )
                    log.info(f"Pipeline complete for {item.document_id}")
                except Exception as e:
                    log.error(f"Pipeline error for {item.document_id}: {e}")
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
