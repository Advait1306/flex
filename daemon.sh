#!/usr/bin/env bash
set -euo pipefail

DAEMON_DIR="$(dirname "$0")/daemon"

if [ "${1:-}" = "bundle" ]; then
    exec "$DAEMON_DIR/bundle.sh"
fi

cd "$DAEMON_DIR"
swift build 2>&1
exec .build/debug/FlexDaemonCLI "$@"
