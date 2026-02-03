#!/bin/bash
set -e

cd "$(dirname "$0")"

ensure_qdrant() {
    if ! docker ps --format '{{.Names}}' | grep -q '^flex-qdrant$'; then
        if docker ps -a --format '{{.Names}}' | grep -q '^flex-qdrant$'; then
            echo "Starting Qdrant container..."
            docker start flex-qdrant
        else
            echo "Qdrant container not found. Run ./install.sh first."
            exit 1
        fi
    fi

    # Wait for Qdrant to be ready
    echo -n "Waiting for Qdrant to be ready"
    until curl -s http://localhost:6333/readyz > /dev/null 2>&1; do
        echo -n "."
        sleep 0.5
    done
    echo " ready!"
}

run_backend() {
    ensure_qdrant
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
    ensure_qdrant
    SESSION="flex"

    # Kill existing session if it exists
    tmux kill-session -t $SESSION 2>/dev/null || true

    # Create new session with backend (keep window open on failure)
    tmux new-session -d -s $SESSION -n backend "cd $(pwd)/backend && uv run uvicorn main:app --reload; echo 'Backend exited. Press enter to close.'; read"

    # Create window for frontend (keep window open on failure)
    tmux new-window -t $SESSION -n frontend "cd $(pwd)/frontend && npm run dev; echo 'Frontend exited. Press enter to close.'; read"

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
