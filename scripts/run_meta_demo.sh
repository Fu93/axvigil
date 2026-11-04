#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${HOME}/.local/bin:${PATH}"

PY="python3"
if [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
fi

cd "$ROOT"
"$PY" scripts/meta_official_flow_demo.py "$@"
