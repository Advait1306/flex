import logging
import sys
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

_file_handler: logging.FileHandler | None = None
_console_handler: logging.StreamHandler | None = None
_initialized = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for the agent pipeline."""
    global _console_handler, _initialized

    if _initialized:
        return

    root_logger = logging.getLogger()
    # Set root to DEBUG so file handler can capture everything
    root_logger.setLevel(logging.DEBUG)

    # Console handler at INFO level
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


def start_pipeline_log() -> Path:
    """Start a new log file for a pipeline run. Returns the log file path."""
    global _file_handler

    # Ensure logging is set up
    setup_logging()

    # Close previous file handler if exists
    if _file_handler:
        root_logger = logging.getLogger()
        root_logger.removeHandler(_file_handler)
        _file_handler.close()

    # Create new log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"pipeline_{timestamp}.log"

    # Create file handler at DEBUG level
    _file_handler = logging.FileHandler(log_file)
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(_file_handler)

    return log_file


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
