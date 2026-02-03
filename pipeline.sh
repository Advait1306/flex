#!/bin/bash
# Usage: ./pipeline.sh "trigger text" [document-id]
cd "$(dirname "$0")/backend"
if [ -n "$2" ]; then
    uv run python cli.py run_pipeline "$1" --document-id "$2"
else
    uv run python cli.py run_pipeline "$1"
fi
