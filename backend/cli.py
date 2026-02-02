#!/usr/bin/env python
"""CLI for testing the agent pipeline."""

import asyncio
import argparse
import json
import uuid
import logging

from agents import run_pipeline
from agents.storage import list_todos, delete_todo
from agents.logging_config import setup_logging, get_logger

log = get_logger("cli")


async def run_on_text(text: str) -> dict:
    """Run pipeline on raw text."""
    # Convert text to BlockNote-like format
    document_content = [{"content": [{"text": text}]}]
    document_id = f"cli-{uuid.uuid4().hex[:8]}"

    log.info(f"Running pipeline on text ({len(text)} chars)")

    result = await run_pipeline(document_id, document_content)
    return result


def main():
    parser = argparse.ArgumentParser(description="Agent pipeline CLI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run_pipeline command
    run_parser = subparsers.add_parser("run_pipeline", help="Run pipeline on text")
    run_parser.add_argument("text", help="Text to process")

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
        result = asyncio.run(run_on_text(args.text))
        print("\n" + "=" * 50)
        print("RESULT:")
        print("=" * 50)
        print(json.dumps(result, indent=2))

    elif args.command == "list_todos":
        todos = list_todos()
        print(json.dumps(todos, indent=2))

    elif args.command == "clear_todos":
        todos = list_todos()
        for todo in todos:
            delete_todo(todo["id"])
        log.info(f"Deleted {len(todos)} todos")


if __name__ == "__main__":
    main()
