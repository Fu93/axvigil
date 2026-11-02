# AxVigil

> Train and certify AI agents that fix smart-contract vulnerabilities.

AxVigil is a hackathon prototype for turning verified smart-contract fixes into portable, on-chain credentials for AI agents. An agent solves a vulnerability challenge, a deterministic verifier checks the patch and proof of concept, and a signed EIP-712 authorization lets the Agent ID owner mint both a tradeable collectible and a non-transferable skill record.

**Meta Global AI Developer Hackathon · BSC testnet · sandbox/whitehat demo**

**Pages.** The project website is in [`web/index.html`](web/index.html), a one-page submission pitch in [`web/pitch.html`](web/pitch.html), and the interactive pipeline demo in [`demo/index.html`](demo/index.html) — all self-contained static pages (no build step; open directly or serve the folder).

**Docs.** [`docs/hackathon-pitch.md`](docs/hackathon-pitch.md) is the concise submission pitch (the built Crucible is the star); [`docs/whitepaper.md`](docs/whitepaper.md) is the full vision — the Crucible that exists today plus the defense network it is the trust root for. Traditional Chinese versions: [`docs/hackathon-pitch.zh-TW.md`](docs/hackathon-pitch.zh-TW.md), [`docs/whitepaper.zh-TW.md`](docs/whitepaper.zh-TW.md).

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
- `challenges/reentrancy-001`: a deliberately vulnerable training fixture with a sample exploit PoC, sample patch and hidden behavior tests.
- `verifier`: deterministic CLI that checks the PoC before and after the patch, runs hidden tests and emits the AxVigil result JSON.
- `backend`: EIP-712 bridge that signs `MintAuth` only for a passed verifier result; it does not submit transactions.
- `contracts/test/VerifierMintIntegration.t.sol`: verifies that the signed verifier hash reaches the mint event and that collectible + skill state are created together.

The platform layers are now integrated on top of the credential layer:

- `mothers/` + `variantgen/`: the anti-memorization engine. Six mother templates (母題) across three vulnerability classes and all three difficulty tiers — reentrancy, price-manipulation, access-control, a legendary signature-replay treasury, plus two real-incident challenges: `bridge-phantom-deposit` (Qubit QBridge, Jan 2022) and `empty-market-inflation` (Hundred Finance / Sonne Compound-fork share inflation) — both already patched and public, self-contained with no fork, and graded so that only the class fix passes (see [`docs/realbank/`](docs/realbank/README.md)). A seed renders a fresh, structurally-unique variant each time (renamed identifiers, distractor functions, reordering), so an agent must fix the bug class, not recall a public answer. Each mother ships 20/20 unique, self-verified variants — 120 in all.
- `verifier/axvigil_verifier/`: the single canonical grader, run in a hardened sandbox (ffi off, no network, wall-clock + POSIX resource limits). Grades both the seed-variant challenges and the patch-based `reentrancy-001` demo (`grade --patch`); zero third-party dependencies.
- `backend/axvigil_backend/`: the platform API — agents `login` with a wallet signature, `start` a server-issued variant (source only), `submit` to be graded in a session, and `authorize` a grade-then-signed reward. SQLite persistence, per-agent rate limits, an answer-leak circuit breaker and a difficulty-weighted leaderboard. `backend/mint_auth.py` remains the single-file signer for the deployed demo.
- `agent/`: an autonomous propose → grade → feed-back → retry solve loop (Meta Model API, with an offline oracle) and a multi-model arena that ranks Muse Spark models on the same variants.
- `demo/`: a self-contained demo page (the loop, anti-memorization, the on-chain skill SVG, and the live testnet deployment).

**Production reward rule.** Each Agent ID gets two lifetime reward attempts. The server deals the challenge: the caller cannot pick the mother or the difficulty, every available mother is equally likely (so basic, advanced, and legendary can all come up), and a fresh variant seed is drawn each time. Opening the session spends the attempt, including if the agent abandons it, lets it expire, or fails the grade — so it cannot reroll until it sees an easy one. A passed attempt can be authorized once, as one collectible mint. The on-chain skill record is written only by that mint, so solves and mints stay 1:1 and neither can exceed 2. Practice mode (`practice: true`) may choose a mother and is not reward-bearing.

**Rarity ladder.** The signed pool must equal the difficulty (the contract rejects a mismatch): basic is a uniform draw, advanced uses multipliers `[1, 2, 4, 8]`, legendary uses `[1, 3, 8, 16]` on Common / Rare / Epic / Legendary. That is a better chance at rarer public tiers, never a guarantee, and still without replacement inside 5444 / 1555 / 622 / 152. The 4 Hidden pieces are drawable only from pool 2, at a fixed 0.25% (25/10000, strictly below 0.30%) that does not rise as other tiers deplete. Pools 0 and 1 never draw Hidden. Hidden counts toward the 7,777 cap and does not consume a public slot, so all 7,773 public pieces stay mintable. Hidden that is not rolled stays unminted. The current BSC testnet collectible includes this roll. See [`SPEC.md`](SPEC.md).

**Tests:** `scripts/test_all.sh` (Foundry + Python). Forge-backed tests fail if `forge` is missing; they discover `solc` from Foundry's svm cache instead of skipping when it is not on `PATH`.

## Contract flow

1. The Agent ID owner completes a vulnerability challenge.
2. The verifier produces a canonical submission hash and pass/fail result.
3. A backend signer creates an EIP-712 `MintAuth` authorization.
4. The Agent ID owner calls `mint` with the authorization and signature.
5. AxVigil mints the collectible and updates the Agent ID's skill record atomically.
6. Collectible rarity can be revealed later using the demo commit-reveal flow.

The contract intentionally uses `_mint`, not `_safeMint`, so the mint path has no receiver callback. Skill records follow the Agent ID registry owner and cannot be transferred independently.

## How a judge runs the demo

From a machine with Foundry and Python 3.10+:

```bash
python3 -m pip install -r backend/requirements.txt
./scripts/judge_demo.sh
```

The script uses public Anvil keys on a local chain only. It warms solc with `forge build`, runs the offline `--oracle` agent (no `META_API_KEY`), deploys the production quotas, and talks to the API with the local MockAgentID as `AGENT_REGISTRY` so login checks `ownerOf`. Reward start is server-random (`practice: true` is how you pick a mother). The mint uses the three-pool ladder: `pool` equals the solved difficulty. The script then reveals the token and prints `tokenURI` plus the on-chain skill metadata.

Shorter slices: `./scripts/demo_pipeline.sh` and `./scripts/local_anvil_demo.sh`. A live model reads `META_API_KEY`, or `MODEL_API_KEY` when that is the only one set.

## Quick start

Install [Foundry](https://book.getfoundry.sh/getting-started/installation) and Python 3.10+. On Windows, use WSL2: Foundry's supported path is Linux, and the verifier's process limits use the POSIX `resource` module. Initialize the submodules, install the Python packages, warm the compiler once (grading stays offline and will not download solc), then run:

```bash
python3 -m pip install -r backend/requirements.txt
git submodule update --init --recursive
cd contracts
forge build          # downloads solc 0.8.28; do this once while online
forge test --no-match-test test_publicQuotasFillWhenHiddenHits
```

`forge` is enough of a Solidity compiler. Set `SOLC` only to pin a binary. If a new shell cannot find `forge`, add `$HOME/.foundry/bin` to `PATH`.

The agent package is not installed by pip. From the repo root:

```bash
PYTHONPATH=agent:verifier python3 -m axvigil_agent solve \
  --challenge challenges/reentrancy-vault --oracle --json
```

The full production-supply distribution test mints and reveals all 7,777 tokens and is intentionally heavier:

```bash
forge test --match-test test_publicQuotasFillWhenHiddenHits
```

`scripts/test_all.sh` runs the Foundry suite (including that full-supply test) plus the Python packages. Last green run: 209 tests (contracts 75 · Python 134). One Docker image check is skipped until `axvigil-sandbox:1.8.7` is built. The live server reference-checks a dealt seed before showing it (`AXVIGIL_REFERENCE_CHECK`, default on) and writes an evidence bundle with a local CIDv1 on each grade. The mined signer rotation, batch-2 reveal, and 2-of-3 mint are recorded in [`docs/operator-runbook.md`](docs/operator-runbook.md). Repeating them still needs keys that stay out of git.

See [`contracts/README.md`](contracts/README.md) for the contract interface, deployment parameters, rarity rules, limitations and BSC testnet deployment instructions.

## Run the first verifier demo

The repository includes a complete reentrancy vertical slice. The single canonical grader
(`axvigil_verifier`, zero third-party deps) grades the deployed `reentrancy-001` demo
directly from its patch:

```bash
PYTHONPATH=verifier python -m axvigil_verifier grade \
  --challenge challenges/reentrancy-001 \
  --patch challenges/reentrancy-001/submissions/sample.patch \
  --poc challenges/reentrancy-001/submissions/sample_poc.t.sol
```

The verifier requires the PoC to pass against the vulnerable baseline, fail after the patch, and leave the hidden tests passing.

The Foundry integration test then checks the contract-side handoff: a valid `MintAuth` mints the collectible, emits the verified `submissionHash`, and records the reentrancy solve on the soulbound skill record. A tampered hash is rejected as an invalid signature.

For a one-command local demonstration of all three layers, run:

```bash
./scripts/demo_pipeline.sh
```

The script uses a deterministic demo-only signer key, never submits a transaction, and runs the verifier, EIP-712 signer and Foundry integration test in sequence.

## Run the local-chain demo

To deploy the contracts and send a real mint transaction on a temporary Anvil chain:

```bash
./scripts/local_anvil_demo.sh
```

This flow starts chain ID `31337`, runs the verifier, passes its `submissionHash` into a Foundry deployment script, deploys `MockAgentID`, `AxVigilSkill` and `AxVigilCollectible`, creates Agent ID `1`, signs `MintAuth`, and broadcasts `mint()`. The script prints the contract addresses, token ID and skill solve count. The private key is Anvil's first deterministic local-only account and must never be used on a public network.

For BSC testnet deployment, first run [`scripts/bsc_preflight.sh`](scripts/bsc_preflight.sh) with a dedicated testnet wallet. The full wallet, faucet, deployment and post-deployment checklist is in [`docs/bsc-testnet-deployment.md`](docs/bsc-testnet-deployment.md).

## BSC testnet deployment (chain 97)

The PR #8 collectible [`0x0658…4658`](https://testnet.bscscan.com/address/0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658) is still the home of token #1 (COMMON, artId 20000) and the Muse Spark signature-replay token #2, now revealed LEGENDARY, artId 320000 (`tokenURI` `320000`). Batch 2 reveal: [`revealSeed`](https://testnet.bscscan.com/tx/0xf83f082999ea63a7bef5f4eacc105e1aa2d648c2be38af1a5ff7fabdb978d597), [`revealTokens`](https://testnet.bscscan.com/tx/0x343f3a8ca91b5c31b5441381900eddf7478e9ed01deeb4e9900338c6273f6ef2). Recompute mismatches: 0. Its signer was rotated to `0x91Ae…e081` ([`setSigner`](https://testnet.bscscan.com/tx/0xaea5242f066736eae950daf093a8cfe44e863e2341e97ab4e08e406f1cea2d3b)).

A separate 2-of-3 collectible is live: [`0x0e87…C8eB`](https://testnet.bscscan.com/address/0x0e8755245231b66FdcE3a625b764dc1Bb597C8eB), skill [`0xE165…5F59`](https://testnet.bscscan.com/address/0xE165C8B4826b6eF7aE84dfe3B1b27017aF1b5F59). Validators `0xc32d…95F9`, `0xD5f5…4645`, `0x133F…ec7f`. Owner `0x94aC…f6E9` is not a validator. Three Muse Spark (`muse-spark-1.1`) sessions each passed on the first request and minted with 2 of 3 signatures (tokens #1–#3, gas 325,555–394,190). `verify_evidence.py` was OK for all three CIDs. Those grades used the subprocess sandbox. Docker isolation is in the repo and was not used on this run.

| Contract | Address | Explorer |
|---|---|---|
| MockAgentID (reused) | `0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e` | [view](https://testnet.bscscan.com/address/0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e) |
| AxVigilSkill | `0x337743Da5894B58039743f46f689337991cECD18` | [view](https://testnet.bscscan.com/address/0x337743Da5894B58039743f46f689337991cECD18) |
| AxVigilCollectible | `0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658` | [view](https://testnet.bscscan.com/address/0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658) |

### Previous deployment (PR #4, superseded)

That superseded bytecode never drew Hidden. AxVigilSkill `0xF572376A24467F5a70D0063448e5386BB842cD30`, AxVigilCollectible [`0x7dd86cB7d4e2d7E0b731FB86D53Bd12D02751685`](https://testnet.bscscan.com/address/0x7dd86cB7d4e2d7E0b731FB86D53Bd12D02751685). Its smoke-test token `1` is unrevealed. Full record under `previous` in the manifest. The current rule, live on the addresses above, draws Hidden only from pool 2 at a fixed 0.25%.

### Original deployment (pre-PR #4, superseded)

The first public testnet deployment (now superseded) is below. The deployment uses the demo-only `MockAgentID` registry and a 50 mint-per-hour cap. Its live demo did commit a batch, mint token `1`, and reveal it (details under the table).

| Contract | Address | Explorer |
|---|---|---|
| MockAgentID | `0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e` | [view](https://testnet.bscscan.com/address/0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e) |
| AxVigilSkill | `0xaCd74265DcFc516bD81d9E7173a57ddEdBD3a593` | [view](https://testnet.bscscan.com/address/0xaCd74265DcFc516bD81d9E7173a57ddEdBD3a593) |
| AxVigilCollectible | `0xFDc7744074d49e9049B82A7CCc76824f75f80437` | [view](https://testnet.bscscan.com/address/0xFDc7744074d49e9049B82A7CCc76824f75f80437) |

The full public deployment record, including transaction hashes, is [`deployments/bsc-testnet-97.json`](deployments/bsc-testnet-97.json).

The collection art plan is documented in [`docs/prd-v1.4-asset-pipeline.md`](docs/prd-v1.4-asset-pipeline.md): Muse Image creates a small Aki source set, while a deterministic local compositor produces the 7,777 final images and metadata. This preserves character consistency, keeps generation cost low and binds the verified vulnerability class to the visual effect.

On that previous deployment, the first live demo completed: verifier `reentrancy-001` passed, Agent ID `1` was created, and Collectible token `1` was minted to the deployer. `AxVigilSkill.totalSolves(1)` was `1` and `currentBatch` was `1`. Those transactions are [commit seed](https://testnet.bscscan.com/tx/0x493ac2cb71504cb643f95c8e1b3a2a7dd53cc33e95428d6cc8297138e100155b), [create Agent ID](https://testnet.bscscan.com/tx/0xc125505638e6562e965977610cbad7a0cfc6f3579c38f3660c24a578a73f5ecd), and [mint collectible](https://testnet.bscscan.com/tx/0xf78ae69add796a107302aaafc178c0b45c4c5936ebcb5ebe47c58f3836b14fce). The reusable script is [`contracts/script/BscLiveDemo.s.sol`](contracts/script/BscLiveDemo.s.sol); its seed is generated and retained locally, never committed.

That original token `1` was revealed as `REENTRANCY`, tier `COMMON`, with `artId = 0`. The [seed reveal transaction](https://testnet.bscscan.com/tx/0x4a0cb0039cd88c8573cab7bd30a909c2d601036f2607b516dc62abe34f407733) and [token reveal transaction](https://testnet.bscscan.com/tx/0xe17d8f2ea32ee87698bc5367aca087ebb12a841083cd2416111aea525dba6401) are under `previous.previous` in the deployment manifest. The current deployment's token `1` was revealed as tier **COMMON**, artId `20000` (see above).

Once a result has `passed: true`, the backend bridge binds its `submissionHash` into the contract's EIP-712 authorization:

```bash
pip install -r backend/requirements.txt
export AXVIGIL_SIGNER_PRIVATE_KEY=0x...
python -m backend.mint_auth --result verifier-result.json \
  --agent-id 1 --to 0xYourAgentOwner --chain-id 97 \
  --verifying-contract 0xYourAxVigilCollectible \
  --nonce 1 --deadline 1790000000
```

## Multi-model arena

The arena is the piece that shows Meta models doing agentic security work. Every contestant receives the same variantgen challenges (the six mothers, rendered from seeds). Each one proposes a patch and a proof of concept, the real verifier grades it, failed checks go back to the model, and it retries until the patch passes or the iteration budget ends. A static leaderboard ranks the results.

What that demonstrates:

- Comparable scores. The mother, the seed, and the verifier are the same for every model, so pass rate is a property of the model and the strategy, not of a friendlier challenge.
- Agentic retries. The loop is propose, grade, read the four failed checks, retry.
- Strategy variants on one model id: `baseline` (submit the patch), `self-critique` (the model reviews its own draft, and the reviewed patch is what gets graded), `plan-then-patch` (a plan completion, then a patch that has to follow it), and `agentic` (a tool-using loop: read files, run the public PoC and public tests, apply a diff, then submit). Hidden tests and the reference solution are not in the tool workspace. The transcript of tool calls and trimmed results is stored on the run as `evidence`.
- An ensemble contestant. Several models propose in order and the verifier keeps the first patch that passes. Later members are not called. That is the orchestration case: models as workers, the verifier as the judge.
- A hard request cap, a concurrency limit, and resume. Completed cells in the results file are skipped and do not spend the cap. The API key is never written to the JSON, the summary, or the progress log.

Set the key on the machine that will call Meta. Do not commit it.

```bash
export META_API_KEY=...                 # MODEL_API_KEY is accepted when META_API_KEY is unset
export META_BASE_URL=https://api.meta.ai/v1   # optional
# META_MAX_TOKENS=4096                  # optional; omit it and the client sends no max_tokens
```

Any model id the Meta API lists can be a contestant, including the Muse Spark line (`muse-spark-1.1`, `muse-spark-1.2`, `muse-spark-1.3`) and contributor variants. Pass the id through as printed. Arena calls use temperature 0. The HTTP timeout is the client default, 300 seconds. `forge` must be on `PATH` (or `FORGE`); warm the compiler once with `cd contracts && forge build` if this machine has not graded before.

Budget-conscious default: 3 models, all 6 mothers, 1 seed, 3 iterations. Worst case for baseline is 3 × 6 × 3 = 54 requests, under a cap of 60.

```bash
PYTHONPATH=agent:verifier:variantgen python -m axvigil_agent arena \
  --contestant muse-spark-1.1 \
  --contestant muse-spark-1.2 \
  --contestant muse-spark-1.3 \
  --mothers reentrancy,price-manipulation,access-control,signature-replay,bridge-phantom-deposit,empty-market-inflation \
  --seeds 1 \
  --max-iters 3 \
  --request-cap 60 \
  --concurrency 1 \
  --out web/arena_results.json \
  --summary web/arena_summary.md
```

Run the same command again to resume. `--fresh` ignores completed rows. `--concurrency 1` keeps the schedule deterministic (contestant, then mother, then seed) and stops on an attempt boundary when the cap is hit. Self-critique and plan-then-patch spend two requests per attempt; an ensemble spends one member's full iteration budget before the next member is asked, so raise `--request-cap` when you add them.

```bash
PYTHONPATH=agent:verifier:variantgen python -m axvigil_agent arena \
  --contestant muse-spark-1.1 \
  --contestant muse-spark-1.2:self-critique \
  --contestant muse-spark-1.3:plan-then-patch \
  --ensemble muse-spark-1.1,muse-spark-1.2,muse-spark-1.3 \
  --seeds 1 --max-iters 3 --request-cap 120 \
  --out web/arena_results.json
```

`web/arena_results.json` is schema version 1 (documented in `agent/axvigil_agent/arena.py`). Each run records pass, attempts, prompt and completion tokens, latency, the checks that failed, and the patch diff size. Agentic runs also record `evidence.transcript`. Ranking is pass rate on completed runs, then fewer total attempts, then fewer total tokens. Open [`web/leaderboard.html`](web/leaderboard.html) beside that file (or serve `web/`). Until a real `arena_results.json` is committed, the page shows a labelled placeholder, not a measured result.

The Meta chat-completions API is OpenAI-compatible, so `--tool-protocol tools` (the default) sends a `tools` array and reads `tool_calls`. `--tool-protocol json` does not send `tools`; the model returns one `{"action","arguments"}` object per turn. Use json when a Muse Spark build ignores tool calls. This repo does not probe the live API.

Small live agentic smoke (2 mothers, 1 seed, at most 4 model rounds each, cap 10). Do not commit the key.

```bash
export META_API_KEY=...
PYTHONPATH=agent:verifier:variantgen python -m axvigil_agent arena \
  --contestant muse-spark-1.1:agentic \
  --mothers reentrancy,access-control \
  --seeds 1 \
  --max-steps 4 \
  --request-cap 10 \
  --tool-protocol tools \
  --concurrency 1 \
  --out web/arena_agentic_smoke.json \
  --summary web/arena_agentic_smoke.md
```

Full arena with a baseline trio plus one agentic contestant. Worst case is about 3 × 6 × 3 baseline requests plus 6 × 6 agentic steps (90). A cap of 120 leaves room for a short retry.

```bash
PYTHONPATH=agent:verifier:variantgen python -m axvigil_agent arena \
  --contestant muse-spark-1.1 \
  --contestant muse-spark-1.2 \
  --contestant muse-spark-1.3 \
  --contestant muse-spark-1.1:agentic \
  --mothers reentrancy,price-manipulation,access-control,signature-replay,bridge-phantom-deposit,empty-market-inflation \
  --seeds 1 \
  --max-iters 3 \
  --max-steps 6 \
  --request-cap 120 \
  --tool-protocol tools \
  --concurrency 1 \
  --out web/arena_results.json \
  --summary web/arena_summary.md
```

## Security and demo scope

This is a hackathon prototype for a BSC testnet/whitehat sandbox. It is not audited and should not be used with production funds. The demo commit-reveal randomness has known owner/validator influence and liveness limitations; the production plan is to replace it with Chainlink VRF v2.5. Admin powers, metadata mutability and skill revocation are documented in [`contracts/README.md`](contracts/README.md).

## License

MIT
