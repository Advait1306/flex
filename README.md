# Flex

Unstructured streaming input processing for Felix

## Project Structure

```
flex/
├── frontend/    # Next.js app (TypeScript, Tailwind CSS)
├── backend/     # FastAPI server
├── install.sh   # Install all dependencies
└── run.sh       # Run servers (supports tmux)
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


## Docs

- [Architecture](docs/architecture.md) — system design, data flow, and storage layout
- [Evals](docs/eval.md) — AI pipeline evaluation framework

## API Endpoints

| Method | Endpoint            | Description                      |
| ------ | ------------------- | -------------------------------- |
| GET    | `/`                 | Hello message                    |
| GET    | `/api/health`       | Health check                     |
| POST   | `/api/pipeline/run` | Run agent pipeline on a document |
| GET    | `/api/todos`        | List all todos                   |
| POST   | `/api/todos`        | Create a todo                    |
| PATCH  | `/api/todos/{id}`   | Update a todo                    |
| DELETE | `/api/todos/{id}`   | Delete a todo                    |
