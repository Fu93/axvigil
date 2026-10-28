import json
from pathlib import Path
from web3 import Web3

ROOT = Path(__file__).resolve().parents[1]


def artifact(name):
    return json.loads(
        (ROOT / "contracts" / "out" / f"{name}.sol" / f"{name}.json").read_text()
    )


class Chain:
    def __init__(self, rpc, registry, collectible, chain_id):
        self.w = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
        self.registry_address = Web3.to_checksum_address(registry)
        self.collectible_address = Web3.to_checksum_address(collectible)
        self.chain_id = chain_id
        self.registry = self.w.eth.contract(
            address=self.registry_address, abi=artifact("MockAgentID")["abi"]
        )
        self.nft = self.w.eth.contract(
            address=self.collectible_address, abi=artifact("AxVigilCollectible")["abi"]
        )
        skill_address = self.nft.functions.skill().call()
        self.skill = self.w.eth.contract(
            address=skill_address, abi=artifact("AxVigilSkill")["abi"]
        )
        if self.w.eth.chain_id != chain_id or chain_id not in (97, 31337):
            raise ValueError("Only BSC testnet (97) or local Anvil (31337) supported")
        if self.nft.functions.agentRegistry().call() != self.registry_address:
            raise ValueError("Registry/collectible configuration mismatch")

    def owner(self, agent):
        return self.registry.functions.ownerOf(agent).call()

    def minted(self, agent):
        return self.nft.functions.mintedPerAgent(agent).call()

    def consumed(self, nonce):
        return self.nft.functions.nonceUsed(nonce).call()

    def eligible(self, agent, wallet):
        return (
            self.owner(agent).lower() == wallet.lower()
            and self.minted(agent) < 2
            and not self.skill.functions.isRevoked(agent).call()
        )

    def open(self):
        return (
            not self.nft.functions.paused().call()
            and self.nft.functions.currentBatch().call() != 0
            and self.nft.functions.totalMinted().call()
            < self.nft.functions.maxSupply().call()
        )

    def info(self):
        return {
            "chainId": self.chain_id,
            "registry": self.registry_address,
            "collectible": self.collectible_address,
            "skill": self.skill.address,
            "minted": self.nft.functions.totalMinted().call(),
            "maxSupply": self.nft.functions.maxSupply().call(),
            "open": self.open(),
        }

    def record(self, agent):
        r = self.skill.functions.getRecord(agent).call()
        return dict(
            zip(
                (
                    "exists",
                    "revoked",
                    "maxDifficulty",
                    "classMask",
                    "totalSolves",
                    "solvesPerClass",
                    "firstSolveAt",
                    "lastSolveAt",
                ),
                r,
            )
        )
