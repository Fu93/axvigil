#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${ROOT}/agent:${ROOT}/verifier:${ROOT}/variantgen"

echo "[1/3] Environment verification..."
echo "Foundry forge: $(which forge 2>/dev/null || echo 'not found')"
echo "Python: $(python3 --version 2>/dev/null || echo 'not found')"
if [ -z "${META_API_KEY:-}" ] && [ -z "${MODEL_API_KEY:-}" ]; then
  echo "Error: META_API_KEY is not set." >&2
  exit 1
fi
echo "Meta API Key: Present"

CHALLENGE="${1:-${ROOT}/challenges/reentrancy-vault}"
MAX_ITERS="${2:-2}"

echo "[2/3] Executing AxVigil Meta Model API Solver against: ${CHALLENGE} (max_iters: ${MAX_ITERS})..."
python3 -u -m axvigil_agent solve --challenge "${CHALLENGE}" --max-iters "${MAX_ITERS}"

echo "[3/3] Meta Model API solve execution complete."
