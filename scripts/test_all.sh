#!/usr/bin/env bash
# Run the full AxVigil test suite (contracts + all Python packages).
# forge must be on PATH (or FORGE). A separate solc binary is optional; tests
# discover the compiler in Foundry's svm cache after `cd contracts && forge build`.
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
