#!/bin/bash
# Get version or set version.
set -euo pipefail
MODE="${1:-}"
if [ "$MODE" = "" ]; then
  uv version
else
  uv version --bump $MODE
  VERSION="$(uv version --short)"
  npm version --allow-same-version --no-git-tag-version "$VERSION"
fi
