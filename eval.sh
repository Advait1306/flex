#!/bin/bash
set -e

cd "$(dirname "$0")/backend"

if [ "$1" = "--generate-fixtures" ]; then
    uv run python -m evals.run --generate-fixtures
    shift
    [ $# -eq 0 ] && exit 0
fi

uv run python -m evals.run "$@"
