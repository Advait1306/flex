#!/bin/bash
set -e

cd "$(dirname "$0")"

run_backend() {
    echo "Starting backend on http://localhost:8000"
    cd backend
    uv run uvicorn main:app --reload
}

run_frontend() {
    echo "Starting frontend on http://localhost:3000"
    cd frontend
    npm run dev
}

run_both() {
    SESSION="flex"

    # Kill existing session if it exists
    tmux kill-session -t $SESSION 2>/dev/null || true

    # Create new session with backend
    tmux new-session -d -s $SESSION -n backend "cd $(pwd)/backend && uv run uvicorn main:app --reload"

    # Create window for frontend
    tmux new-window -t $SESSION -n frontend "cd $(pwd)/frontend && npm run dev"

    # Attach to session
    echo "Starting servers in tmux session '$SESSION'"
    echo "  - Backend:  http://localhost:8000"
    echo "  - Frontend: http://localhost:3000"
    echo ""
    echo "Attaching to tmux... (Ctrl+B D to detach)"
    tmux attach -t $SESSION
}

case "$1" in
    backend|b)
        run_backend
        ;;
    frontend|f)
        run_frontend
        ;;
    *)
        run_both
        ;;
esac
