#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${HOME}/.local/bin:${PATH}"

PY="python3"
if [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
fi

echo "== verifier =="
(cd "$ROOT/verifier" && "$PY" -m pytest -q)

echo "== variantgen =="
(cd "$ROOT/variantgen" && PYTHONPATH=. "$PY" -m pytest -q)

echo "== backend protocol =="
(cd "$ROOT/backend" && PYTHONPATH=. "$PY" -m pytest tests/ -q)

echo "== mint-auth bridge =="
(cd "$ROOT" && "$PY" -m pytest backend/test_mint_auth.py -q)

echo "== agent protocol client =="
(cd "$ROOT/agent" && PYTHONPATH=. "$PY" -m pytest tests/ -q)

echo "ALL PYTHON SUITES GREEN"
