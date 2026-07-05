#!/bin/bash
set -euo pipefail
export UV_CACHE_DIR="${UV_CACHE_DIR:-/opt/data/.uv-cache}"
exec uv run --script "$(dirname "$0")/news_scout/main.py"
