"""Independent validators and a coordinator for threshold MintAuth signatures.

A validator re-runs the deterministic grade from an evidence bundle and signs
the coordinator's MintAuth only when that grade passes and the bundle's
submissionHash matches. It does not trust the coordinator's pass bit.

`scripts/run_validators.py` serves one validator over HTTP. Tests call
`consider` in-process.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .evidence import recompute_submission_hash
from .signer import AuthSigner


class GradeRefused(Exception):
    """This validator will not sign."""


@dataclass
class LocalValidator:
    private_key: str
    chain_id: int
    verifying_contract: str

    def consider(self, manifest: dict, auth: dict, grade_fn) -> dict:
        """Return {signer, signature} or raise GradeRefused.

        `grade_fn(manifest) -> dict` must include `passed`. The real server
        passes a function that re-renders the mother and calls the grader.
        """
        expected = recompute_submission_hash(manifest)
        recorded = manifest.get("submissionHash")
        if expected != recorded:
            raise GradeRefused("submissionHash does not match the bundle")
        if str(auth.get("submissionHash", "")).lower() != str(recorded).lower():
            raise GradeRefused("MintAuth submissionHash does not match the bundle")
        result = grade_fn(manifest)
        if not result or not result.get("passed"):
            raise GradeRefused("independent grade did not pass")
        signed = AuthSigner(self.private_key, self.chain_id, self.verifying_contract).sign_prepared_mint(auth)
        return {"signer": signed.signer, "signature": signed.signature, "digest": signed.digest}


def collect_signatures(validators: list[LocalValidator], manifest: dict, auth: dict, k: int, grade_fn) -> list[dict]:
    """Ask each validator. Return the first `k` signatures that agreed."""
    if k < 1:
        raise GradeRefused("threshold must be at least 1")
    agreed: list[dict] = []
    refusals: list[str] = []
    for validator in validators:
        try:
            agreed.append(validator.consider(manifest, auth, grade_fn))
        except GradeRefused as exc:
            refusals.append(str(exc))
        if len(agreed) >= k:
            return agreed[:k]
    raise GradeRefused(
        f"need {k} signatures, got {len(agreed)}; refusals: {refusals}"
    )


def manifest_from_path(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
