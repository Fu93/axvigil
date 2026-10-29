# Shared checks for the demo scripts. Source this; do not execute it.
# Expects ROOT to be the repository root.

preflight_python() {
  python3 -c "import eth_account, fastapi" >/dev/null 2>&1 || {
    echo "Python packages are missing. From the repo root run:" >&2
    echo "  python3 -m pip install -r backend/requirements.txt" >&2
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
    (cd "$ROOT/contracts" && forge build >/dev/null)
  fi
}
