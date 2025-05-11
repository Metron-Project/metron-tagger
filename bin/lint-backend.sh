#!/bin/bash
# Lint checks
set -euxo pipefail

####################
###### Python ######
####################
uv run ruff check .
uv run ruff format --check .
# uv run pyright
uv run vulture --exclude "*/.venv/*.py,*/.tox/*.py,*/node_modules/*.py,*/tests/*.py" .

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run lint
