#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Installing backend dependencies..."
cd backend
uv venv
uv pip install -r requirements.txt
cd ..

echo ""
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "Done! Run ./run.sh to start the servers."
