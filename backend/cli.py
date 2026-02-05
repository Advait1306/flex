#!/usr/bin/env python
"""CLI for testing the agent pipeline."""

import asyncio
import argparse
import json
import logging

from ai import run_freewrite_processor_agent
from store import list_todos, delete_todo
from ai.logging_config import setup_logging, get_logger

log = get_logger("cli")


async def run_on_text(text: str, use_context: bool = False) -> None:
    """Run pipeline on text trigger with optional freewrite context."""
    from store import load_freewrite

    document_content = None

    if use_context:
        log.info("Loading freewrite for context")
        document_content = load_freewrite()
        if document_content is None:
            log.warning("No freewrite content found")

    log.info(f"Running pipeline on trigger ({len(text)} chars)")

    await run_freewrite_processor_agent(
        trigger=text, document_context=document_content or "", document_id="freewrite"
    )


def main():
    parser = argparse.ArgumentParser(description="Agent pipeline CLI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run_pipeline command
    run_parser = subparsers.add_parser("run_pipeline", help="Run pipeline on text")
    run_parser.add_argument("text", help="Trigger text to process")
    run_parser.add_argument("--context", "-c", action="store_true", help="Include freewrite content as context")

    # list_todos command
    subparsers.add_parser("list_todos", help="List all todos")

    # clear_todos command
    subparsers.add_parser("clear_todos", help="Delete all todos")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level)

    if args.command == "run_pipeline":
        log.info("Starting pipeline")
        asyncio.run(run_on_text(args.text, args.context))

    elif args.command == "list_todos":
        todos = list_todos()
        print(json.dumps([t.model_dump(exclude_none=True) for t in todos], indent=2))

    elif args.command == "clear_todos":
        todos = list_todos()
        for todo in todos:
            delete_todo(todo.id)
        log.info(f"Deleted {len(todos)} todos")


if __name__ == "__main__":
    main()
