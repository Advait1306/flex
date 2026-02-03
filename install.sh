#!/bin/bash
set -e

cd "$(dirname "$0")"

# Backend venv and dependencies
echo "Checking backend dependencies..."
cd backend
if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment..."
    uv venv
else
    echo "  Virtual environment already exists, skipping..."
fi

echo "  Installing Python dependencies..."
uv sync

# Qdrant container
echo ""
echo "Checking Qdrant container..."
if docker ps -a --format '{{.Names}}' | grep -q '^flex-qdrant$'; then
    if docker ps --format '{{.Names}}' | grep -q '^flex-qdrant$'; then
        echo "  Qdrant container already running, skipping..."
    else
        echo "  Starting existing Qdrant container..."
        docker start flex-qdrant
    fi
else
    echo "  Creating and starting Qdrant container..."
    docker-compose up -d
fi
cd ..

# Frontend dependencies
echo ""
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "Done! Run ./run.sh to start the servers."
