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

# Docker containers (Qdrant + Postgres)
echo ""
echo "Starting Docker containers..."
docker compose up -d
cd ..

# Frontend dependencies
echo ""
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "Done! Run ./run.sh to start the servers."
