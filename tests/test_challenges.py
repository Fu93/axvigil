import pytest
from challenges.generator import generate, reference
from verifier.policy import validate, submission_hash
from verifier.worker import grade


@pytest.mark.parametrize("v", range(3))
def test_twenty_distinct_reproducible_variants(v):
    variants = [generate(v, i) for i in range(20)]
    assert len({x.fingerprint for x in variants}) == 20
    assert generate(v, 7) == generate(v, 7)
    for c in variants:
        patch, poc = reference(c)
        assert validate(c.code, patch, poc) < 80


@pytest.mark.parametrize("v", range(3))
def test_real_evm_reference_and_unchanged_patch(v):
    c = generate(v, 42)
    patch, poc = reference(c)
    result = grade(dict(vulnClass=v, seed=42, patch=patch, poc=poc))
    assert result["passed"], result
    result = grade(dict(vulnClass=v, seed=42, patch=c.code, poc=poc))
    assert (
        result["pocProvesBug"]
        and not result["pocFailsAfterPatch"]
        and not result["passed"]
    ), result


@pytest.mark.parametrize("v", range(3))
def test_revert_everything_does_not_earn_credit(v):
    c = generate(v, 42)
    _, poc = reference(c)
    # A disabled contract prevents exploitation but must fail normal functionality.
    patch = "pragma solidity ^0.8.28; contract Challenge { fallback() external payable { revert(); } }"
    result = grade(dict(vulnClass=v, seed=42, patch=patch, poc=poc))
    assert not result["passed"] and not result["hiddenTestsPass"]


def test_noop_poc_and_input_policy():
    c = generate(0, 42)
    patch, _ = reference(c)
    poc = "pragma solidity ^0.8.28; contract Attack { function run(address) external payable {} }"
    result = grade(dict(vulnClass=0, seed=42, patch=patch, poc=poc))
    assert not result["pocProvesBug"] and not result["passed"]
    with pytest.raises(ValueError):
        validate(c.code, 'import "../../.env";', poc)
    with pytest.raises(ValueError):
        validate(c.code, "x" * 24001, poc)
    assert submission_hash("a", "b") != submission_hash("b", "a")
