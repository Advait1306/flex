#!/usr/bin/env python
"""CLI for managing users."""

import argparse
import asyncio
import os

import bcrypt
from tortoise import Tortoise

DB_URL = os.getenv("DATABASE_URL", "postgres://flex:flex@localhost:5433/flex")


async def init_db():
    await Tortoise.init(
        db_url=DB_URL,
        modules={"models": ["db_models"]},
    )
    await Tortoise.generate_schemas()


async def create_user(username: str, password: str):
    await init_db()
    from db_models import User

    if await User.filter(username=username).exists():
        print(f"Error: user '{username}' already exists")
        return

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = await User.create(username=username, password_hash=password_hash)
    print(f"Created user '{user.username}' (id={user.id})")
    await Tortoise.close_connections()


async def list_users():
    await init_db()
    from db_models import User

    users = await User.all()
    if not users:
        print("No users found")
    for user in users:
        print(f"  id={user.id}  username={user.username}  created_at={user.created_at}")
    await Tortoise.close_connections()


async def delete_user(username: str):
    await init_db()
    from db_models import User

    deleted = await User.filter(username=username).delete()
    if deleted:
        print(f"Deleted user '{username}'")
    else:
        print(f"User '{username}' not found")
    await Tortoise.close_connections()


def main():
    parser = argparse.ArgumentParser(description="Manage users")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a user")
    create_parser.add_argument("username")
    create_parser.add_argument("password")

    subparsers.add_parser("list", help="List all users")

    delete_parser = subparsers.add_parser("delete", help="Delete a user")
    delete_parser.add_argument("username")

    args = parser.parse_args()

    if args.command == "create":
        asyncio.run(create_user(args.username, args.password))
    elif args.command == "list":
        asyncio.run(list_users())
    elif args.command == "delete":
        asyncio.run(delete_user(args.username))


if __name__ == "__main__":
    main()
