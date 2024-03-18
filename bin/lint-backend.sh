#!/bin/bash
# Lint checks
set -euxo pipefail

####################
###### Python ######
####################
poetry run ruff check .
poetry run ruff format --check .
# poetry run pyright
poetry run vulture --exclude "*/venv/*.py,*/.tox/*.py,*/node_modules/*.py,*/tests/*.py" .

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run lint
npm run remark-check
