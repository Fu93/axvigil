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

from eth_utils import keccak

from .evidence import canonical_json, recompute_submission_hash
from .signer import AuthSigner


class GradeRefused(Exception):
    """This validator will not sign."""


def verdict_reason_hash(evidence: bytes, reason: str) -> str:
    """keccak256(keccak256(evidence) || utf8(reason)). Both validators must use this."""
    return "0x" + keccak(keccak(evidence) + reason.encode("utf-8")).hex()


def challenge_grade(manifest: dict, live_grade, *, recheck: bool, allow_test_grade: bool) -> dict:
    """Decide pass/fail for a challenge re-grade.

    `AXV_ALLOW_TEST_GRADE` honours `manifest["axvTestGradePassed"]` and the sentinel
    `counterexample == "fail"` so a demo can show both verdicts without forge.
    Leave that flag off in production: the live grader result is what gets signed.
    """
    if allow_test_grade and "axvTestGradePassed" in manifest:
        passed = bool(manifest["axvTestGradePassed"])
        if passed and manifest.get("counterexample") == "fail":
            return {"passed": False, "reason": "counterexample"}
        return {"passed": passed, "reason": "test-grade"}
    if not recheck:
        return {"passed": True, "reason": "recheck-off"}
    result = dict(live_grade(manifest) or {})
    if result.get("reason") == "counterexample" or result.get("counterexampleHit"):
        result["passed"] = False
        result["reason"] = "counterexample"
        return result
    passed = bool(result.get("passed"))
    result["passed"] = passed
    result["reason"] = "regrade-passed" if passed else "regrade-failed"
    return result


@dataclass
class LocalValidator:
    private_key: str
    chain_id: int
    verifying_contract: str
    challenge_contract: str = ""

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

    def consider_challenge(
        self,
        token_id: int,
        manifest: dict,
        grade_fn,
        evidence: bytes,
        round_num: int = 1,
        challenger: str = "0x0000000000000000000000000000000000000000",
    ) -> dict:
        """Re-grade `manifest` and sign ChallengeVerdict. Does not trust a claimed pass bit.

        `evidence` must be the exact bytes the challenger will pass to `challenge`.
        The reason hash commits to keccak256(evidence) plus the grade reason.
        `upheld` is true only when the independent grade does not pass.
        """
        if not self.challenge_contract:
            raise GradeRefused("CHALLENGE_CONTRACT is not set")
        expected = recompute_submission_hash(manifest)
        recorded = manifest.get("submissionHash")
        if expected != recorded:
            raise GradeRefused("submissionHash does not match the bundle")
        if canonical_json(manifest) != evidence:
            raise GradeRefused("evidence bytes are not the canonical manifest")
        result = grade_fn(manifest) or {}
        passed = bool(result.get("passed"))
        reason = str(result.get("reason") or ("regrade-passed" if passed else "regrade-failed"))
        upheld = not passed
        reason_hash = verdict_reason_hash(evidence, reason)
        evidence_hash = "0x" + keccak(evidence).hex()
        signed = AuthSigner(self.private_key, self.chain_id, self.challenge_contract).sign_verdict(
            token_id=int(token_id),
            round_num=int(round_num),
            challenger=challenger,
            evidence_hash=evidence_hash,
            upheld=upheld,
            reason_hash=reason_hash,
        )
        return {
            "signer": signed.signer,
            "signature": signed.signature,
            "digest": signed.digest,
            "upheld": upheld,
            "reasonHash": reason_hash,
            "passed": passed,
            "reason": reason,
            "evidenceHash": evidence_hash,
        }


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
