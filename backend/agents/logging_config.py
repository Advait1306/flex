import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

_console_handler: logging.StreamHandler | None = None
_initialized = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure console logging for the agent pipeline."""
    global _console_handler, _initialized

    if _initialized:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console handler
    _console_handler = logging.StreamHandler(sys.stdout)
    _console_handler.setLevel(level)
    _console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root_logger.addHandler(_console_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    setup_logging()
    return logging.getLogger(name)


class AgentLog:
    """Dedicated log for agent actions and results.

    This is separate from Python's logging system and only captures
    what we explicitly write to it - agent actions, tool calls, and results.
    """

    _instance: "AgentLog | None" = None
    _file: Any = None
    _path: Path | None = None

    @classmethod
    def start(cls) -> Path:
        """Start a new agent log file. Returns the log file path."""
        if cls._file:
            cls._file.close()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cls._path = LOGS_DIR / f"agent_{timestamp}.log"
        cls._file = open(cls._path, "w")
        cls._write_header()
        return cls._path

    @classmethod
    def _write_header(cls) -> None:
        """Write log header."""
        if cls._file:
            cls._file.write(f"Agent Log - Started {datetime.now().isoformat()}\n")
            cls._file.write("=" * 80 + "\n\n")
            cls._file.flush()

    @classmethod
    def _timestamp(cls) -> str:
        return datetime.now().strftime("%H:%M:%S")

    @classmethod
    def section(cls, title: str) -> None:
        """Start a new section in the log."""
        if cls._file:
            cls._file.write(f"\n{'=' * 40}\n")
            cls._file.write(f"[{cls._timestamp()}] {title}\n")
            cls._file.write(f"{'=' * 40}\n")
            cls._file.flush()

    @classmethod
    def action(cls, agent: str, action: str, details: str | None = None) -> None:
        """Log an agent action."""
        if cls._file:
            cls._file.write(f"[{cls._timestamp()}] [{agent}] ACTION: {action}\n")
            if details:
                for line in details.split("\n"):
                    cls._file.write(f"    {line}\n")
            cls._file.flush()

    @classmethod
    def tool_call(cls, tool_name: str, args: dict | str) -> None:
        """Log a tool call."""
        if cls._file:
            cls._file.write(f"[{cls._timestamp()}] TOOL CALL: {tool_name}\n")
            if isinstance(args, dict):
                for key, value in args.items():
                    cls._file.write(f"    {key}: {value}\n")
            else:
                cls._file.write(f"    {args}\n")
            cls._file.flush()

    @classmethod
    def tool_result(cls, tool_name: str, result: str, truncate: int = 500) -> None:
        """Log a tool result."""
        if cls._file:
            display_result = result[:truncate] + "..." if len(result) > truncate else result
            cls._file.write(f"[{cls._timestamp()}] TOOL RESULT ({tool_name}):\n")
            for line in display_result.split("\n"):
                cls._file.write(f"    {line}\n")
            cls._file.flush()

    @classmethod
    def decision(cls, agent: str, decision: str, reason: str) -> None:
        """Log an agent decision."""
        if cls._file:
            cls._file.write(f"[{cls._timestamp()}] [{agent}] DECISION: {decision}\n")
            cls._file.write(f"    Reason: {reason}\n")
            cls._file.flush()

    @classmethod
    def result(cls, agent: str, result: str) -> None:
        """Log an agent result."""
        if cls._file:
            cls._file.write(f"[{cls._timestamp()}] [{agent}] RESULT: {result}\n")
            cls._file.flush()

    @classmethod
    def error(cls, agent: str, error: str) -> None:
        """Log an error."""
        if cls._file:
            cls._file.write(f"[{cls._timestamp()}] [{agent}] ERROR: {error}\n")
            cls._file.flush()

    @classmethod
    def close(cls) -> None:
        """Close the log file."""
        if cls._file:
            cls._file.write(f"\n{'=' * 80}\n")
            cls._file.write(f"Agent Log - Ended {datetime.now().isoformat()}\n")
            cls._file.close()
            cls._file = None
            cls._path = None
