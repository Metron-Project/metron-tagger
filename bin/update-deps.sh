#!/bin/bash
# Update python dependencies
set -euo pipefail
poetry update
poetry show --outdated
npm update
npm outdated
