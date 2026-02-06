# Flex Backend

## Setup

1. Start services:
   ```bash
   docker compose up -d
   ```

2. Create a user:
   ```bash
   uv run python manage_users.py create <username> <password>
   ```

3. Start the backend:
   ```bash
   uv run uvicorn main:app --reload
   ```

## User Management

```bash
uv run python manage_users.py create <username> <password>
uv run python manage_users.py list
uv run python manage_users.py delete <username>
```
