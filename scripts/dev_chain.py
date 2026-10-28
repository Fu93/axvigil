"""Deploy the existing contracts on local Anvil; no public-chain funds or keys."""

import json
from pathlib import Path
import secrets
from eth_account import Account
from web3 import Web3
from backend.chain import artifact


def deploy(w, name, sender, *args):
    a = artifact(name)
    f = w.eth.contract(abi=a["abi"], bytecode=a["bytecode"]["object"])
    r = w.eth.wait_for_transaction_receipt(
        f.constructor(*args).transact({"from": sender, "gas": 12000000})
    )
    if r.status != 1:
        raise RuntimeError("Deployment failed: " + name)
    return w.eth.contract(address=r.contractAddress, abi=a["abi"])


def main():
    w = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    if w.eth.chain_id != 31337:
        raise ValueError("Local Anvil chain 31337 only")
    owner = w.eth.accounts[0]
    key = Account.create().key.hex()
    registry = deploy(w, "MockAgentID", owner)
    skill = deploy(w, "AxVigilSkill", owner, registry.address, owner)
    nft = deploy(
        w,
        "AxVigilCollectible",
        owner,
        registry.address,
        skill.address,
        Account.from_key(key).address,
        owner,
        [5444, 1555, 622, 152, 4],
        50,
    )
    w.eth.wait_for_transaction_receipt(
        skill.functions.grantRole(
            Web3.keccak(text="MINTER_ROLE"), nft.address
        ).transact({"from": owner})
    )
    seed = secrets.token_bytes(32)
    w.eth.wait_for_transaction_receipt(
        nft.functions.commitSeed(Web3.keccak(seed)).transact({"from": owner})
    )
    w.eth.wait_for_transaction_receipt(
        registry.functions.mintId(owner, 1).transact({"from": owner})
    )
    path = Path(".env.local")
    token = secrets.token_urlsafe(48)
    path.write_text(
        f"RPC_URL=http://127.0.0.1:8545\nCHAIN_ID=31337\nAGENT_REGISTRY={registry.address}\nCOLLECTIBLE={nft.address}\nSIGNER_URL=http://127.0.0.1:8001\nSIGNER_SERVICE_TOKEN={token}\nDATABASE_PATH=artifacts/local.sqlite\n"
    )
    path.chmod(0o600)
    Path(".env.signer.local").write_text(
        path.read_text() + f"MINT_SIGNER_KEY=0x{key}\n"
    )
    Path(".env.signer.local").chmod(0o600)
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/local-reveal.json").write_text(
        json.dumps({"collectible": nft.address, "batch": 1, "seed": "0x" + seed.hex()})
    )
    Path("artifacts/local-reveal.json").chmod(0o600)
    print(
        f"Local contracts deployed. Agent ID 1 belongs to {owner}. Config: .env.local and .env.signer.local"
    )
    print(
        "Import an Anvil development account into a dedicated test wallet. Never fund that account on a public network."
    )


if __name__ == "__main__":
    main()
