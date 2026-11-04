# Shared checks for the demo scripts. Source this; do not execute it.
# Expects ROOT to be the repository root.

export PATH="${HOME}/.foundry/bin:${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

PY="${PY:-python3}"
if [ -x "${ROOT:-}/.venv/bin/python" ]; then
    PY="${ROOT}/.venv/bin/python"
elif [ -x "${ROOT:-}/.venv/Scripts/python.exe" ]; then
    PY="${ROOT}/.venv/Scripts/python.exe"
fi

preflight_python() {
  "$PY" -c "import eth_account, fastapi" >/dev/null 2>&1 || {
    echo "Python packages are missing. From the repo root run:" >&2
    echo "  $PY -m pip install -r backend/requirements.txt" >&2
    exit 2
  }
}

preflight_forge() {
  command -v forge >/dev/null 2>&1 || {
    echo "forge is not on PATH. Install Foundry, then open a new shell:" >&2
    echo "  curl -L https://foundry.paradigm.xyz | bash && foundryup" >&2
    echo "  export PATH=\"\$PATH:\$HOME/.foundry/bin\"" >&2
    exit 2
  }
  # Offline grading cannot download solc. One online build fills Foundry's cache.
  if [[ "${SKIP_FORGE_BUILD:-}" != 1 ]]; then
    echo "Warming the Solidity compiler cache (forge build)..." >&2
    (cd "$ROOT/contracts" && forge build --skip script >/dev/null)
  fi
}
