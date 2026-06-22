#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python -m smart_labelimg.app
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 -m smart_labelimg.app
fi
exec python -m smart_labelimg.app
