#!/usr/bin/env bash
# Jalankan ZOI mode development di workspace pengembangan: backend (8000, Mock Provider) + Vite (5173).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ZOI_MODE=development
(cd "$ROOT/backend" && .venv/bin/python -m app) &
BACKEND=$!
trap 'kill $BACKEND 2>/dev/null' EXIT
cd "$ROOT/frontend" && npm run dev
