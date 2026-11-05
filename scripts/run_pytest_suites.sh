#!/usr/bin/env bash
set -e
export PATH="$HOME/.foundry/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"

echo "== verifier =="
(cd "$ROOT/verifier" && $UV run --with pytest pytest -q)

echo "== variantgen =="
(cd "$ROOT/variantgen" && PYTHONPATH=. $UV run --with pytest pytest -q)

echo "== backend protocol =="
(cd "$ROOT/backend" && PYTHONPATH=. $UV run --with pytest pytest tests/ -q)

echo "== mint-auth bridge =="
(cd "$ROOT" && $UV run --with pytest pytest backend/test_mint_auth.py -q)

echo "== agent protocol client =="
(cd "$ROOT/agent" && PYTHONPATH=".:../verifier:../backend" $UV run --with pytest --with fastapi --with httpx pytest tests/ -q)

echo "ALL PYTHON SUITES COMPLETED"
