#!/bin/bash
cd "$(dirname "$0")/backend" && uv run python cli.py run_pipeline "$1"
