"""Backend configuration from environment variables."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    signer_key: str | None
    chain_id: int
    verifying_contract: str | None
    challenges_dir: Path
    verifier_dir: Path
    forge_bin: str
    solc_bin: str | None
    grade_timeout_s: int
    auth_ttl_s: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            signer_key=os.environ.get("SIGNER_KEY"),
            chain_id=int(os.environ.get("CHAIN_ID", "97")),
            verifying_contract=os.environ.get("VERIFYING_CONTRACT"),
            challenges_dir=Path(os.environ.get("CHALLENGES_DIR", REPO_ROOT / "challenges")),
            verifier_dir=Path(os.environ.get("VERIFIER_DIR", REPO_ROOT / "verifier")),
            forge_bin=os.environ.get("FORGE") or (shutil.which("forge") or "forge"),
            solc_bin=os.environ.get("SOLC") or shutil.which("solc"),
            grade_timeout_s=int(os.environ.get("GRADE_TIMEOUT_S", "120")),
            auth_ttl_s=int(os.environ.get("AUTH_TTL_S", "3600")),
        )

    @property
    def can_sign(self) -> bool:
        return bool(self.signer_key and self.verifying_contract)
