#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${ROOT}/agent:${ROOT}/verifier"
cd "$ROOT"

python3 -m axvigil_agent solve --challenge challenges/reentrancy-vault --oracle --json
