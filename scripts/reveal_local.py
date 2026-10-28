"""Local demo operator: reveal current batch, draw tiers, open another batch."""

import json
from pathlib import Path
import secrets
from web3 import Web3
from backend.chain import artifact


def main():
    w = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    if w.eth.chain_id != 31337:
        raise ValueError("Local Anvil only")
    p = Path("artifacts/local-reveal.json")
    state = json.loads(p.read_text())
    nft = w.eth.contract(
        address=state["collectible"], abi=artifact("AxVigilCollectible")["abi"]
    )
    owner = w.eth.accounts[0]
    for fn in [
        nft.functions.revealSeed(state["batch"], state["seed"]),
        nft.functions.revealTokens(200),
    ]:
        r = w.eth.wait_for_transaction_receipt(
            fn.transact({"from": owner, "gas": 15000000})
        )
        assert r.status == 1
    seed = secrets.token_bytes(32)
    r = w.eth.wait_for_transaction_receipt(
        nft.functions.commitSeed(Web3.keccak(seed)).transact({"from": owner})
    )
    assert r.status == 1
    state.update(batch=nft.functions.currentBatch().call(), seed="0x" + seed.hex())
    p.write_text(json.dumps(state))
    p.chmod(0o600)
    print(
        "Pending tokens revealed; next batch opened. This is operator-trusted demo randomness."
    )


if __name__ == "__main__":
    main()
