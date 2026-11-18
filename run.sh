#!/usr/bin/env bash
# Start the todo app in the DKubeX workspace.
#
# Publish it first:
#   d3x app create --name todo-app --display-name "Todo List" \
#                  --description "A simple todo list backed by PostgreSQL" --icon icon.svg
# That writes .dkubex-app.env next to this script.
set -euo pipefail
cd "$(dirname "$0")"

# PORT and DKUBEX_BASE_PATH come from the workspace, not from this file. `set -a` exports
# every variable the file defines so the server below inherits them.
set -a
. ./.dkubex-app.env
set +a

# Optional local overrides: a .env in this directory (copied from .env.example) is read for
# DATABASE_URL. The workspace's nginx reaches the app over loopback on $PORT; --root-path
# tells FastAPI its prefix so URLs it generates are correct.
if [ -f .env ]; then set -a; . ./.env; set +a; fi

exec ./.venv/bin/uvicorn main:app --host 0.0.0.0 --port "$PORT" --root-path "$DKUBEX_BASE_PATH"
