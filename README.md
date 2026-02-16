# Flex

AI-powered task management with voice input and ambient context capture.

## Project Structure

```
flex/
├── frontend/    # Next.js app (TypeScript, Tailwind CSS)
├── backend/     # FastAPI server (LangChain agents, Qdrant, Postgres)
├── daemon/      # macOS menu bar daemon (Swift, Accessibility API)
├── docs/        # Architecture and daemon docs
├── install.sh   # Install all dependencies
├── run.sh       # Run servers (supports tmux)
└── daemon.sh    # Build and run daemon CLI
```

## Prerequisites

- Docker must be running before starting the app

## Quick Start

```bash
./install.sh    # Install all dependencies
./run.sh        # Run both servers in tmux
```

## Running Servers

```bash
./run.sh            # Run both (frontend + backend) in tmux
./run.sh frontend   # Run frontend only (or: ./run.sh f)
./run.sh backend    # Run backend only (or: ./run.sh b)
```

When running both, use `Ctrl+B D` to detach from tmux.

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

## Daemon

macOS menu bar app that captures ambient context from running apps (Slack, Linear, browsers, etc.) and sends snapshots to the backend for processing.

```bash
# CLI debugging tool
./daemon.sh --tree Slack              # AX tree extraction
./daemon.sh --tree "Google Chrome"    # Chromium active tab
./daemon.sh --tree Safari --raw       # Raw AX tree dump

# Build .app bundle
./daemon.sh bundle
```

See [docs/daemon.md](docs/daemon.md) for details on app categories, extraction strategies, and change detection.

## Docs

- [Architecture](docs/architecture.md) — system design, data flow, and storage layout
- [Daemon](docs/daemon.md) — macOS daemon extraction strategies and change detection
- [Evals](docs/eval.md) — AI pipeline evaluation framework

## API Endpoints

| Method | Endpoint                    | Description                          |
| ------ | --------------------------- | ------------------------------------ |
| GET    | `/`                         | Hello message                        |
| GET    | `/api/health`               | Health check                         |
| POST   | `/api/pipeline/run`         | Run agent pipeline on a document     |
| GET    | `/api/todos`                | List all todos                       |
| GET    | `/api/todos/{id}`           | Get a todo                           |
| POST   | `/api/todos`                | Create a todo                        |
| PATCH  | `/api/todos/{id}`           | Update a todo                        |
| DELETE | `/api/todos/{id}`           | Delete a todo                        |
| GET    | `/api/facts`                | List all facts                       |
| GET    | `/api/freewrite`            | Get freewrite document               |
| PUT    | `/api/freewrite`            | Update freewrite document            |
| GET    | `/api/auth/check`           | Validate auth token                  |
| POST   | `/api/transcription/session`| Create ephemeral transcription token |
| POST   | `/api/daemon/snapshot`      | Receive daemon content snapshot      |
