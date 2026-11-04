#!/usr/bin/env bash
# Run the full AxVigil test suite (contracts + all Python packages).
# forge must be on PATH (or FORGE). A separate solc binary is optional; tests
# discover the compiler in Foundry's svm cache after `cd contracts && forge build`.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${PATH}"

PY="python3"
if [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
fi

echo "== forge build (src + script) ==" && (cd "$ROOT/contracts" && forge build && forge build script)
echo "== contracts =="            && (cd "$ROOT/contracts" && forge test)
echo "== verifier =="             && (cd "$ROOT/verifier"  && "$PY" -m pytest -q)
echo "== variantgen =="           && (cd "$ROOT/variantgen" && PYTHONPATH=. "$PY" -m pytest -q)
echo "== backend protocol =="     && (cd "$ROOT/backend"   && PYTHONPATH=. "$PY" -m pytest tests/ -q)
echo "== mint-auth bridge =="     && (cd "$ROOT"           && "$PY" -m pytest backend/test_mint_auth.py -q)
echo "== agent protocol client ==" && (cd "$ROOT/agent"     && PYTHONPATH=. "$PY" -m pytest tests/ -q)
echo "ALL GREEN"
