#!/usr/bin/env bash
# Build frontend → frontend/apps/web/dist (disajikan backend di mode local). Node hanya dibutuhkan di sini.
set -euo pipefail
cd "$(dirname "$0")/../frontend"
npm ci --no-audit --no-fund
npm run build
