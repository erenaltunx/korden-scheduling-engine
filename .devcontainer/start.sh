#!/usr/bin/env bash
set -euo pipefail
# Avoid spawning duplicate servers if Codespaces resumes an existing environment.
if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  exit 0
fi
nohup python -m uvicorn korden.api:app --host 0.0.0.0 --port 8000 > /tmp/korden-web.log 2>&1 < /dev/null &
