#!/usr/bin/env python
"""CLI for testing the agent pipeline."""

import asyncio
import argparse
import json
import logging
import os

from ai import run_freewrite_processor_agent
from store import list_todos, delete_todo
from ai.logging_config import setup_logging, get_logger

log = get_logger("cli")

DB_URL = os.getenv("DATABASE_URL", "postgres://flex:flex@localhost:5433/flex")


async def init_db():
    from tortoise import Tortoise

    await Tortoise.init(
        db_url=DB_URL,
        modules={"models": ["db_models"]},
    )


async def resolve_user_id(username: str) -> int | None:
    """Resolve a username to a user ID via the database."""
    await init_db()
    from db_models import User

    user = await User.filter(username=username).first()
    if user is None:
        log.error(f"User '{username}' not found")
        return None
    return user.id


async def run_on_text(text: str, use_context: bool = False, username: str | None = None) -> None:
    """Run pipeline on text trigger with optional freewrite context."""
    if not username:
        log.error("--user is required")
        return

    user_id = await resolve_user_id(username)
    if user_id is None:
        return

    document_content = None

    if use_context:
        from store import load_freewrite

        log.info(f"Loading freewrite for user '{username}'")
        document_content = await load_freewrite(user_id)
        if document_content is None:
            log.warning("No freewrite content found")

    log.info(f"Running pipeline on trigger ({len(text)} chars)")

    await run_freewrite_processor_agent(
        trigger=text, document_context=document_content or "", document_id="freewrite",
        user_id=user_id,
    )


def main():
    parser = argparse.ArgumentParser(description="Agent pipeline CLI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run_pipeline command
    run_parser = subparsers.add_parser("run_pipeline", help="Run pipeline on text")
    run_parser.add_argument("text", help="Trigger text to process")
    run_parser.add_argument("--context", "-c", action="store_true", help="Include freewrite content as context")
    run_parser.add_argument("--user", "-u", required=True, help="Username")

    # list_todos command
    list_parser = subparsers.add_parser("list_todos", help="List all todos for a user")
    list_parser.add_argument("--user", "-u", required=True, help="Username")

    # clear_todos command
    clear_parser = subparsers.add_parser("clear_todos", help="Delete all todos for a user")
    clear_parser.add_argument("--user", "-u", required=True, help="Username")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level)

    if args.command == "run_pipeline":
        log.info("Starting pipeline")
        asyncio.run(run_on_text(args.text, args.context, args.user))

    elif args.command == "list_todos":
        user_id = asyncio.run(resolve_user_id(args.user))
        if user_id is None:
            return
        todos = list_todos(user_id=user_id)
        print(json.dumps([t.model_dump(exclude_none=True) for t in todos], indent=2))

    elif args.command == "clear_todos":
        user_id = asyncio.run(resolve_user_id(args.user))
        if user_id is None:
            return
        todos = list_todos(user_id=user_id)
        for todo in todos:
            delete_todo(todo.id)
        log.info(f"Deleted {len(todos)} todos")


if __name__ == "__main__":
    main()
