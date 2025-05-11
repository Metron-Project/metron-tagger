#!/bin/bash
# Update python dependencies
set -euo pipefail
uv sync --no-install-project --all-extras --upgrade
uv tree --outdated
npm update
npm outdated
