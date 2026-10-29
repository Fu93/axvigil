#!/usr/bin/env bash
# Run the full AxVigil test suite (contracts + all Python packages).
# forge + solc must be reachable (PATH, or FORGE/SOLC env).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${PATH}"

echo "== contracts =="            && (cd "$ROOT/contracts" && forge test)
echo "== verifier =="             && (cd "$ROOT/verifier"  && python3 -m pytest -q)
echo "== variantgen =="           && (cd "$ROOT/variantgen" && PYTHONPATH=. python3 -m pytest -q)
echo "== backend protocol =="     && (cd "$ROOT/backend"   && PYTHONPATH=. python3 -m pytest tests/ -q)
echo "== mint-auth bridge =="     && (cd "$ROOT"           && python3 -m pytest backend/test_mint_auth.py -q)
echo "== agent protocol client ==" && (cd "$ROOT/agent"     && PYTHONPATH=. python3 -m pytest tests/ -q)
echo "ALL GREEN"
