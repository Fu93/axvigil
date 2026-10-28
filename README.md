# AxVigil

**AI agents for smart contract security — verified fixes, not just findings.**

AxVigil is a testnet prototype for training and certifying agents that repair Solidity
vulnerabilities. A solve requires an actual exploit on the original, a patch that stops it,
and successful functional checks. One signed mint creates two outcomes: an Agent ID skill
record and a collectible NFT.

**Status:** implemented local prototype; not audited, not mainnet-ready. BSC testnet deployment
and real Muse model runs require operator credentials. No production deployment is included.
The build follows the supplied PRD v1.2 and the repository's existing `SPEC.md` interfaces;
see [delivery status](docs/STATUS.md) for the exact scope and gaps.

## What works

- Three original teaching fixtures: reentrancy, manipulable spot price, missing owner guard.
- Seeded generation and persistent source-hash deduplication; reference-solution preflight
  runs before every challenge is issued and its timer begins.
- Real PoC execution as **Anvil transactions**, without Forge VM cheatcodes. The grader
  measures victim state itself. Both original and patch are compiled with Foundry.
- Twenty-four functional cases per patch, including authorization, accounting, interleaved
  deposits, credit bounds and a functional gas ceiling. An unchanged or revert-only patch fails.
- Disposable offline Docker grader with resource limits. The API refuses to fall back to
  local execution when Docker is absent. The signer key never enters the grader.
- EIP-712 nonce login, registry ownership checks, persistent SQLite sessions/tasks, bounded
  worker capacity, request limits, a pass-rate circuit breaker, idempotent mint authorization.
- Existing Foundry contracts: fixed production supply of 7,777, two mints per Agent ID,
  hourly cap, pause, signer rotation, commit-reveal tiers, revocable Agent ID skill record.
- Browser wallet workbench, fragment reader, patch/PoC editors, verification results,
  actual wallet mint transaction and on-chain skill record view. No frontend build step.
- Configurable Muse chat-completions adapter and command-line solve/submit loop.

## Local quick start

Requires Python 3.12+, Git, [Foundry v1.7.1](https://getfoundry.sh/), and Docker Engine.
The frontend and API run together; the signer is a separate loopback-only process.

```bash
git clone --recurse-submodules https://github.com/Fu93/axvigil.git
cd axvigil
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
forge build --root contracts
docker build -f verifier/Dockerfile -t axvigil-grader:local .
```

In a separate terminal start a **local development chain**:

```bash
anvil --host 127.0.0.1 --chain-id 31337
```

Deploy local contracts and create Agent ID 1:

```bash
python -m scripts.dev_chain
```

Start the signer in its own terminal:

```bash
set -a
. ./.env.signer.local
set +a
uvicorn backend.signer:create_signer --factory --host 127.0.0.1 --port 8001
```

Start the API in another terminal **without loading the signer key**:

```bash
set -a
. ./.env.local
set +a
uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Connect a dedicated test wallet using the first account printed
by Anvil. Add local RPC `http://127.0.0.1:8545`, chain ID `31337`, currency `ETH` in that wallet.
All Anvil default accounts are publicly known: never use them with real funds.

Enter Agent ID `1`, sign in, draw a challenge, submit complete `Challenge` and `Attack`
sources, then mint through the wallet. The UI waits for a successful receipt before reporting
success. Operator reveal, from the repository root:

```bash
python -m scripts.reveal_local
```

This reveals pending tiers and opens a new batch. Commit-reveal trusts the operator and
has no timeout fallback; it is not VRF. See [contract caveats](contracts/README.md).

## Verification

```bash
forge test --root contracts
pytest -q
python -m scripts.calibrate --variants 20
python -m scripts.sandbox_smoke  # requires the Docker image built above
```

The calibration command runs trusted, repository-owned reference code directly on local
Anvil to verify solvability across 3 × 20 source variants. **Do not substitute this path
for the Docker boundary for external submissions.** It does not measure Muse pass rates.
CI runs contract tests, Python tests, the 60-variant matrix and Docker smoke tests.

## Muse agent

Set the exact model ID and chat-completions URL supplied by your provider. No endpoint or
model ID is assumed, and no model run is represented as successful without credentials.

```bash
export MUSE_CHAT_COMPLETIONS_URL=https://YOUR_VERIFIED_ENDPOINT
export MUSE_MODEL=YOUR_MODEL_ID
export MUSE_API_KEY=YOUR_KEY
export AGENT_WALLET_KEY=0xYOUR_DEDICATED_LOCAL_OR_TESTNET_AGENT_KEY
python -m agent.solve --agent-id 1 --class 0
```

The CLI signs login, reads all fragments, requests a JSON patch/PoC, submits, polls, and saves
the signed mint authorization after a pass. It does not automatically send a transaction.
Adapter uses a chat-completions-compatible schema; a native Muse schema may need adaptation.
Muse Image is not yet integrated. Solver artifacts and all local key/config files are ignored
by Git. Local reveal seeds are stored only in `artifacts/`.

## BSC testnet

See [deployment runbook](docs/DEPLOYMENT.md). The deploy script refuses chains other than 97;
the backend supports only 97 and local 31337. No mainnet RPC is passed to a grader. A testnet
MockAgentID is deliberately open-mint and provides **no Sybil protection**.

## API

`/docs` exposes the OpenAPI schema. These are HTTP endpoints, not an MCP server.

| Action | Endpoint |
|---|---|
| Protocol / chain state | `GET /api/protocol_info` |
| Prepare EIP-712 login | `POST /api/prepare` with wallet, agentId |
| Exchange signature for session | `POST /api/login` with nonce, signature |
| Draw + validate reference | `POST /api/start` with vulnClass (0..2), returns 202 |
| Read source | `GET /api/challenges/{id}/fragments/{index}` |
| Submit complete sources | `POST /api/challenges/{id}/submit` with patch, poc, returns 202 |
| Poll state/results | `GET /api/challenges/{id}/status` |
| Obtain idempotent authorization + calldata | `POST /api/challenges/{id}/authorize` |
| Read on-chain capability | `GET /api/skills/{agentId}` |

Authenticated actions use `Authorization: Bearer <session>`. A challenge lasts one hour;
sessions last two hours; mint authorizations last ten minutes. IDs, nonces and deadlines
in mint responses are decimal strings to preserve uint256 precision in JavaScript.
Failed solves do not consume on-chain quota. Ownership is checked again on every authenticated
action and by the collectible contract when minting. A transferred ID retains its mint quota.

## Repository

| Directory | Purpose |
|---|---|
| `contracts/` | Existing Foundry contracts, tests and BSC testnet deploy script |
| `challenges/` | Seed generator, internal reference fixtures and source attribution |
| `verifier/` | Policy, disposable Docker runner and trusted EVM evaluator |
| `backend/` | FastAPI API, SQLite persistence, EIP-712 encoding and separate signer |
| `agent/` | Configurable Muse-compatible solver CLI |
| `web/` | Static, accessible wallet workbench |
| `scripts/`, `tests/` | Local deployment, reveal, solvability matrix and integration tests |

Only local synthetic/testnet exercises are authorized here. No production targets, real
funds, audit guarantees, tokens or yield promises. New code is MIT; upstream submodules
retain their respective licences. [Security model](SECURITY.md) · [Task provenance](challenges/SOURCES.md)
