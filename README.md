# Flex

A monorepo with a Next.js frontend and FastAPI backend.

## Project Structure

```
flex/
├── frontend/    # Next.js app (TypeScript, Tailwind CSS)
├── backend/     # FastAPI server
├── install.sh   # Install all dependencies
└── run.sh       # Run servers (supports tmux)
```

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

## Manual Setup

### Backend

```bash
cd backend
uv venv
uv pip install -r requirements.txt
uv run uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Agent Pipeline

Run the LangGraph agent pipeline to extract tasks from text:

```bash
./pipeline.sh "Buy milk, fix login bug, call mom"
```

## API Endpoints

| Method | Endpoint      | Description         |
|--------|---------------|---------------------|
| GET    | `/`           | Hello message       |
| GET    | `/api/health` | Health check        |
| POST   | `/api/pipeline/run` | Run agent pipeline on a document |
| GET    | `/api/todos`  | List all todos      |
| POST   | `/api/todos`  | Create a todo       |
| PATCH  | `/api/todos/{id}` | Update a todo   |
| DELETE | `/api/todos/{id}` | Delete a todo   |
