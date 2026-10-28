"""Run ONLY in the disposable grader, or on trusted local reference fixtures.
PoCs execute as real Anvil transactions, never in Forge's cheatcode-enabled test VM.
"""

import json
from pathlib import Path
import random
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from web3 import Web3
from challenges.generator import generate
from verifier.policy import validate, submission_hash

GAS = 3_000_000


def compile_source(source, name, root):
    root = Path(root)
    (root / "src").mkdir(parents=True)
    (root / "src" / f"{name}.sol").write_text(source)
    (root / "foundry.toml").write_text(
        '[profile.default]\nsolc_version="0.8.28"\nevm_version="cancun"\nffi=false\nfs_permissions=[]\noptimizer=true\n'
    )
    subprocess.run(
        ["forge", "build", "--offline", "--root", str(root)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=35,
    )
    artifact = json.loads((root / "out" / f"{name}.sol" / f"{name}.json").read_text())
    return artifact


@contextmanager
def chain():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [
            "anvil",
            "--silent",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--hardfork",
            "cancun",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    w = Web3(
        Web3.HTTPProvider(f"http://127.0.0.1:{port}", request_kwargs={"timeout": 5})
    )
    try:
        for _ in range(100):
            if w.is_connected():
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("Anvil did not start")
        yield w
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def deploy(w, artifact, sender):
    factory = w.eth.contract(
        abi=artifact["abi"], bytecode=artifact["bytecode"]["object"]
    )
    receipt = w.eth.wait_for_transaction_receipt(
        factory.constructor().transact({"from": sender, "gas": GAS})
    )
    if receipt.status != 1:
        raise ValueError("Contract deployment failed")
    return w.eth.contract(address=receipt.contractAddress, abi=artifact["abi"])


def tx(w, function, sender, value=0, required=True):
    r = w.eth.wait_for_transaction_receipt(
        function.transact({"from": sender, "value": value, "gas": GAS})
    )
    if required and r.status != 1:
        raise ValueError("Required functionality reverted")
    return r


def fund(w, target, sender, value):
    r = w.eth.wait_for_transaction_receipt(
        w.eth.send_transaction(
            {"from": sender, "to": target.address, "value": value, "gas": 100000}
        )
    )
    if r.status != 1:
        raise ValueError("Funding reverted")


def attack_trial(w, artifact, attack_artifact, c):
    owner, user, attacker = w.eth.accounts[:3]
    target, attack = deploy(w, artifact, owner), deploy(w, attack_artifact, attacker)
    unit = 10**16
    if c.vulnClass == 0:
        tx(w, target.functions.deposit(), user, unit * 10)
    else:
        fund(w, target, user, unit * 10)
    tx(w, attack.functions.run(target.address), attacker, unit, required=False)
    # Trusted objective measures victim state, not the participant's test return value.
    if c.vulnClass == 0:
        return w.eth.get_balance(target.address) < unit * 10
    if c.vulnClass == 1:
        return (
            target.functions.debt(attack.address).call()
            > target.functions.collateral(attack.address).call() // 2
        )
    return (
        target.functions.owner().call() != owner
        or w.eth.get_balance(target.address) < unit * 10
    )


def functionality(w, artifact, c):
    owner, alice, bob = w.eth.accounts[:3]
    target = deploy(w, artifact, owner)
    rng = random.Random(c.seed ^ 0xA871)
    peak = 0
    for i in range(24):
        user = (alice, bob)[i % 2]
        amount = rng.randrange(10**12, 10**16)
        if c.vulnClass == 0:
            # Leave another user's deposit in reserve throughout each withdrawal.
            other = owner
            reserve = amount // 7
            tx(w, target.functions.deposit(), other, reserve)
            tx(w, target.functions.deposit(), user, amount)
            assert target.functions.credit(user).call() == amount
            before = w.eth.get_balance(target.address)
            r = tx(w, target.functions.withdraw(), user)
            assert target.functions.credit(user).call() == 0
            assert w.eth.get_balance(target.address) == before - amount
            assert target.functions.credit(other).call() == reserve
            tx(w, target.functions.withdraw(), other)
            assert w.eth.get_balance(target.address) == 0
            assert tx(w, target.functions.withdraw(), user, required=False).status == 0
        elif c.vulnClass == 1:
            # Fresh lending fixture per case, manipulated spot must not affect credit limits.
            target = deploy(w, artifact, owner)
            fund(w, target, owner, amount * 10)
            tx(w, target.functions.deposit(), user, amount)
            tx(w, target.functions.moveSpot(c.parameter * rng.randrange(2, 100)), bob)
            before = w.eth.get_balance(target.address)
            r = tx(w, target.functions.borrow(amount // 3), user)
            assert w.eth.get_balance(target.address) == before - amount // 3
            assert target.functions.debt(user).call() == amount // 3
            assert (
                tx(w, target.functions.borrow(amount), user, required=False).status == 0
            )
            assert (
                tx(
                    w, target.functions.setTrusted(c.parameter * 2), bob, required=False
                ).status
                == 0
            )
            tx(w, target.functions.setTrusted(c.parameter * 2), owner)
            tx(w, target.functions.borrow(amount // 3), user)
        else:
            old_owner = target.functions.owner().call()
            assert (
                tx(w, target.functions.setOwner(bob), alice, required=False).status == 0
            )
            assert (
                tx(w, target.functions.sweep(alice, 0), alice, required=False).status
                == 0
            )
            next_owner = bob if old_owner == owner else owner
            tx(w, target.functions.setOwner(next_owner), old_owner)
            fund(w, target, alice, amount)
            before = w.eth.get_balance(alice)
            r = tx(w, target.functions.sweep(alice, amount), next_owner)
            assert w.eth.get_balance(alice) == before + amount
        peak = max(peak, r.gasUsed)
        assert r.gasUsed < 180000, "Functional gas ceiling exceeded"
    return True


def grade(payload):
    c = generate(int(payload["vulnClass"]), int(payload["seed"]))
    result = dict(
        challengeId=c.challengeId,
        seed=c.seed,
        vulnClass=c.vulnClass,
        difficulty=c.difficulty,
        pocProvesBug=False,
        pocFailsAfterPatch=False,
        hiddenTestsPass=False,
        patchWithinLimits=False,
        passed=False,
        solveSeconds=payload.get("solveSeconds"),
        submissionHash=submission_hash(payload["patch"], payload["poc"]),
    )
    try:
        validate(c.code, payload["patch"], payload["poc"])
        result["patchWithinLimits"] = True
        with tempfile.TemporaryDirectory() as temp:
            original = compile_source(c.code, "Challenge", Path(temp) / "original")
            patched = compile_source(
                payload["patch"], "Challenge", Path(temp) / "patched"
            )
            attack = compile_source(payload["poc"], "Attack", Path(temp) / "attack")
            with chain() as w:
                result["pocProvesBug"] = attack_trial(w, original, attack, c)
                result["pocFailsAfterPatch"] = not attack_trial(w, patched, attack, c)
                try:
                    result["hiddenTestsPass"] = functionality(w, patched, c)
                except (AssertionError, ValueError):
                    pass
        result["passed"] = all(
            result[k]
            for k in (
                "pocProvesBug",
                "pocFailsAfterPatch",
                "hiddenTestsPass",
                "patchWithinLimits",
            )
        )
        result["log"] = (
            "Verified on local synthetic Anvil state; 24 functional/invariant cases."
        )
    except Exception as exc:
        # Never return compiler logs or host paths to participants.
        result["log"] = f"Verification failed: {type(exc).__name__}"
    return result


if __name__ == "__main__":
    import sys

    print(json.dumps(grade(json.loads(Path(sys.argv[1]).read_text()))))
