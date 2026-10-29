"""Backend configuration from environment variables."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _discover_solc() -> str | None:
    """SOLC env, PATH, or Foundry's svm cache. None lets forge use its own solver."""
    env = os.environ.get("SOLC")
    if env:
        return env
    found = shutil.which("solc")
    if found:
        return found
    verifier = REPO_ROOT / "verifier"
    if str(verifier) not in sys.path:
        sys.path.insert(0, str(verifier))
    try:
        from axvigil_verifier.toolchain import discover_solc
    except Exception:
        return None
    return discover_solc()


@dataclass
class Settings:
    signer_key: str | None
    chain_id: int
    verifying_contract: str | None
    challenges_dir: Path
    verifier_dir: Path
    variantgen_dir: Path
    mothers_dir: Path
    challenge_cache_dir: Path
    db_path: str
    session_secret: str
    forge_bin: str
    solc_bin: str | None
    grade_timeout_s: int
    auth_ttl_s: int
    session_ttl_s: int
    start_rate_per_min: float
    submit_rate_per_min: float
    agent_registry: str | None = None
    rpc_url: str | None = None
    # Local dev only. Production must leave this false and set AGENT_REGISTRY + RPC_URL.
    dev_skip_ownership: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        skip = os.environ.get("AXVIGIL_DEV_SKIP_OWNERSHIP", "").strip().lower() in ("1", "true", "yes")
        return cls(
            signer_key=os.environ.get("SIGNER_KEY"),
            chain_id=int(os.environ.get("CHAIN_ID", "97")),
            verifying_contract=os.environ.get("VERIFYING_CONTRACT"),
            challenges_dir=Path(os.environ.get("CHALLENGES_DIR", REPO_ROOT / "challenges")),
            verifier_dir=Path(os.environ.get("VERIFIER_DIR", REPO_ROOT / "verifier")),
            variantgen_dir=Path(os.environ.get("VARIANTGEN_DIR", REPO_ROOT / "variantgen")),
            mothers_dir=Path(os.environ.get("MOTHERS_DIR", REPO_ROOT / "mothers")),
            challenge_cache_dir=Path(os.environ.get("CHALLENGE_CACHE_DIR", "/tmp/axvigil-challenges")),
            db_path=os.environ.get("DB_PATH", str(REPO_ROOT / "backend" / "axvigil.db")),
            session_secret=os.environ.get("SESSION_SECRET", "dev-only-insecure-secret-change-me"),
            forge_bin=os.environ.get("FORGE") or (shutil.which("forge") or "forge"),
            solc_bin=_discover_solc(),
            grade_timeout_s=int(os.environ.get("GRADE_TIMEOUT_S", "120")),
            auth_ttl_s=int(os.environ.get("AUTH_TTL_S", "3600")),
            session_ttl_s=int(os.environ.get("SESSION_TTL_S", "1800")),
            start_rate_per_min=float(os.environ.get("START_RATE_PER_MIN", "12")),
            submit_rate_per_min=float(os.environ.get("SUBMIT_RATE_PER_MIN", "30")),
            agent_registry=os.environ.get("AGENT_REGISTRY") or None,
            rpc_url=os.environ.get("RPC_URL") or os.environ.get("BSC_TESTNET_RPC") or None,
            dev_skip_ownership=skip,
        )

    @property
    def can_sign(self) -> bool:
        key = (self.signer_key or "").strip()
        contract = (self.verifying_contract or "").strip()
        if not key or not contract:
            return False
        body = contract.lower().removeprefix("0x")
        # A zero placeholder must not turn signing on.
        return bool(body) and set(body) != {"0"}
