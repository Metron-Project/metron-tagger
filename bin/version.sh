#!/bin/bash
# Get version or set version in Frontend & API.
set -euo pipefail
VERSION="${1:-}"
if [ "$VERSION" = "" ]; then
  uv version
else
  uv version
  npm version --allow-same-version --no-git-tag-version "$VERSION"
fi
