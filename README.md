# AxVigil

> Train and certify AI agents that fix smart-contract vulnerabilities.

AxVigil is a hackathon prototype for turning verified smart-contract fixes into portable, on-chain credentials for AI agents. An agent solves a vulnerability challenge, a deterministic verifier checks the patch and proof of concept, and a signed EIP-712 authorization lets the Agent ID owner mint both a tradeable collectible and a non-transferable skill record.

**Meta Global AI Developer Hackathon · BSC testnet · sandbox/whitehat demo**

## Why AxVigil

AI coding agents can generate patches, but it is difficult to distinguish a plausible answer from a fix that actually removes an exploit without breaking the contract. AxVigil connects four pieces:

```text
challenge → AI-generated patch + PoC → deterministic verifier → signed on-chain credential
```

The credential is bound to a SPACE ID-style Agent ID rather than a wallet. The collectible records the challenge category and difficulty, while the ERC-5192 skill record accumulates the agent's verified vulnerability-solving history.

## Current repository status

The current public prototype implements the smart-contract credential layer:

- `AxVigilCollectible`: ERC-721 collectible with EIP-712 mint authorization, fixed tier pools, staged rarity release, commit-reveal demo randomness, per-Agent ID quota, hourly cap and pause controls.
- `AxVigilSkill`: ERC-5192-style soulbound skill record bound to an Agent ID, with vulnerability-class counts, maximum difficulty, revocation and on-chain SVG metadata.
- `MockAgentID`: open-mint ERC-721 registry used only for local tests and demos.
- `contracts/test`: unit, fuzz, rarity-distribution and invariant tests.

The broader challenge, verifier, agent, backend and web layers are described in [`SPEC.md`](SPEC.md) and are being built as separate demo components.

## Contract flow

1. The Agent ID owner completes a vulnerability challenge.
2. The verifier produces a canonical submission hash and pass/fail result.
3. A backend signer creates an EIP-712 `MintAuth` authorization.
4. The Agent ID owner calls `mint` with the authorization and signature.
5. AxVigil mints the collectible and updates the Agent ID's skill record atomically.
6. Collectible rarity can be revealed later using the demo commit-reveal flow.

The contract intentionally uses `_mint`, not `_safeMint`, so the mint path has no receiver callback. Skill records follow the Agent ID registry owner and cannot be transferred independently.

## Quick start

Install [Foundry](https://book.getfoundry.sh/getting-started/installation), initialize the submodules, then run:

```bash
git submodule update --init --recursive
cd contracts
forge build
forge test --no-match-test test_productionFullSupply
```

The full production-supply distribution test mints and reveals all 7,777 tokens and is intentionally heavier:

```bash
forge test --match-test test_productionFullSupply
```

See [`contracts/README.md`](contracts/README.md) for the contract interface, deployment parameters, rarity rules, limitations and BSC testnet deployment instructions.

## Security and demo scope

This is a hackathon prototype for a BSC testnet/whitehat sandbox. It is not audited and should not be used with production funds. The demo commit-reveal randomness has known owner/validator influence and liveness limitations; the production plan is to replace it with Chainlink VRF v2.5. Admin powers, metadata mutability and skill revocation are documented in [`contracts/README.md`](contracts/README.md).

## License

MIT
