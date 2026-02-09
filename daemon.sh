#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/daemon"
swift build 2>&1
exec .build/debug/FlexDaemonCLI "$@"
