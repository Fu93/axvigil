# Optimistic challenge window

Anyone can recompute a minted record. The chain does not re-run Foundry. It stores the anchor, holds a bond, and accepts a fresh validator threshold as the verdict.

## What is deployed

`script/DeployChallenge.s.sol` deploys three contracts and wires them:

| Contract | Role |
|---|---|
| `AxVigilCollectible` | Same mint rules as before (single-use `submissionHash`, 2 mints per Agent ID, hourly cap, k-of-n `MintAuth`). `setChallengeBook` is called once before the first mint. |
| `AxVigilSkill` | Soulbound record. A solve is pending until `confirmSolve`. `isValid(agentId)` is true only when the record exists, is not admin-revoked, and at least one solve is confirmed. |
| `AxVigilChallenge` | The window, the bonds, and `ChallengeVerdict`. |

`MintAuth` is unchanged and is still signed against the **collectible** (domain name `AxVigil`, version `1`). Verdicts are a different type, signed against the **challenge book**:

```text
ChallengeVerdict(uint256 tokenId,uint32 round,address challenger,bytes32 evidenceHash,bool upheld,bytes32 reasonHash)
```

With no book, or with `challengeWindow == 0`, `mint` confirms the skill in the same transaction and `status` is Final. Existing tests and the previous deploy scripts keep that behaviour. A non-zero window snapshots `readyAt` per token, so a later `setChallengeWindow` does not move an open record.

## State machine

`status(tokenId)` is `0 None`, `1 Pending`, `2 Challenged`, `3 Final`, `4 Revoked`. The same numbers are returned by the collectible, which reads the book.

1. `mint` escrows `operatorBond` (zero when the window is zero) and emits `EvidenceAnchored(tokenId, submissionHash, challengeDeadline)`. The hash is the lookup key for the off-chain bundle and its CIDv1. The contract does not store the CID bytes.
2. Until `readyAt`, anyone may `challenge(tokenId, evidence)` with `msg.value == challengeBond`. `evidence` is opaque (canonical manifest bytes in the demo). The book stores `keccak256(evidence)` and emits `Challenged`.
3. `resolveChallenge(tokenId, upheld, reasonHash, signatures)` checks `threshold` distinct current validators. It does not trust the challenger.
   - **Upheld:** `Revoked`. The collectible is flagged (`flagged`, not burned, so supply and rarity accounting stay put). The pending skill solve is removed. The challenger is credited their bond plus the operator escrow, or `protocolReward` from the pool when the escrow was zero and the pool can cover the whole reward. A short pool still revokes; it just pays no extra reward. The lifetime mint quota is not refunded.
   - **Rejected:** the challenger's bond is credited to `treasury`. Another challenge is allowed while the window is still open, so an operator cannot burn the only slot with a throwaway challenge.
4. If validators never sign, anyone may `expireChallenge` after the snapshotted `respondBy`. The bond is returned (validator silence is not the challenger's fault) and another challenge is allowed until `readyAt`. Delay is therefore bounded by `challengeWindow + responseWindow`.
5. `finalize(tokenId)` after `readyAt`, with no open challenge and no upheld verdict, confirms the skill solve, emits `Finalized`, and credits the operator escrow back.

`status` becomes Final as soon as the window has passed. `isValid` stays false until `finalize`, because that transaction is what returns the bond and confirms the credential together. `finalize` is permissionless.

Payouts are pull-based (`withdraw`). A reverting recipient cannot brick `resolveChallenge`, and the withdraw path is non-reentrant.

## Why a separate book

The collectible is already near the size where more mint logic gets tight, and bond accounting wants its own balance invariant: `escrowed + bondsHeld + poolBalance + claimable == address(book).balance`. Keeping ETH out of the NFT contract means a challenge bug cannot move mint fees that do not exist there. The tradeoff is a second verifying contract for verdicts, and a one-time `setChallengeBook` before mint. The book reads `isValidator` and `threshold` from the collectible, so there is still one validator set.

## Validator `/challenge`

`scripts/run_validators.py` still serves `POST /sign`. It also serves:

```text
POST /challenge
{"tokenId": 1, "round": 1, "challenger": "0x...", "manifest": { ... the evidence bundle ... }}
```

The process re-grades. `upheld` is true only when that grade does not pass. The reason hash is `keccak256(keccak256(evidence) || utf8(reason))` where `evidence` is the canonical manifest JSON (the same bytes passed to `challenge`). A manifest field `counterexample` that contains a Foundry test is run against the patched sources when the base grade passed; a passing exploit test flips the verdict to upheld (`reason = "counterexample"`).

`AXV_ALLOW_TEST_GRADE=1` honours `manifest.axvTestGradePassed` (and `counterexample: "fail"`) so the demo can show both paths without a forge grade. Leave that variable unset on a validator that protects a real mint. `RECHECK=0` skips forge and treats a grade as passing; do not use it for a real challenge.

## Demo

Local anvil (public development keys, no testnet transactions):

```bash
./scripts/run_challenge_demo.sh
```

The script deploys, starts three validators, mints an honest record (validators sign `/sign`), mints a bad record only after `/sign` refuses it (the script then collude-signs with `VALIDATOR_KEY_*`), challenges the bad record, resolves the upheld verdict, advances the clock, and finalizes the honest record. It prints a JSON summary of token ids, gas, and bond amounts.

BSC testnet (chain 97). This broadcasts. Fund the deployer and the challenger first. Default gas price is 1 gwei legacy.

```bash
export DEMO_TARGET=bsc
export I_UNDERSTAND_THIS_SENDS_TESTNET_TX=1
export RPC_URL="${BSC_TESTNET_RPC:-https://bsc-testnet-rpc.publicnode.com}"
export AXVIGIL_CHALLENGE_ENV=/path/to/challenge.env   # optional; sourced, never committed
export PRIVATE_KEY=0x...          # deployer, owner, and agent operator
export CHALLENGER_KEY=0x...
export VALIDATOR_KEY_1=0x...
export VALIDATOR_KEY_2=0x...
export VALIDATOR_KEY_3=0x...
export CHALLENGE_WINDOW=120       # seconds; use 3600 for an hour-long window
export RESPONSE_WINDOW=3600
export CHALLENGE_BOND=1000000000000000    # 0.001 tBNB
export OPERATOR_BOND=2000000000000000     # 0.002 tBNB
export GAS_PRICE=1000000000               # 1 gwei
./scripts/run_challenge_demo.sh
```

`SIGNER`, `VALIDATOR_2`, and `VALIDATOR_3` are derived from the three validator keys when omitted. `THRESHOLD` defaults to 2. To reuse a deploy, set `AXVIGIL_COLLECTIBLE`, `AXVIGIL_SKILL`, `AXVIGIL_CHALLENGE`, and `AGENT_REGISTRY` before running; the script skips `forge script` in that case. On BSC the process sleeps `CHALLENGE_WINDOW + 20` seconds. Anvil uses `anvil_increaseTime` instead.

A real forge re-grade (no test sentinel) needs a manifest the grader can render (`motherId`, `seed`, `patch`, `poc`) and:

```bash
export AXV_ALLOW_TEST_GRADE=0
export RECHECK=1
```

The HTTP body is the same. The demo script itself builds synthetic manifests, so use `AXV_ALLOW_TEST_GRADE=1` with `./scripts/run_challenge_demo.sh`.

### Env vars

| Variable | Meaning |
|---|---|
| `DEMO_TARGET` | `anvil` (default) or `bsc` |
| `I_UNDERSTAND_THIS_SENDS_TESTNET_TX` | must be `1` for `DEMO_TARGET=bsc` |
| `RPC_URL` / `BSC_TESTNET_RPC` | endpoint |
| `CHAIN_ID` | `31337` or `97` |
| `PRIVATE_KEY` | deployer and agent operator |
| `CHALLENGER_KEY` | posts the challenge bond |
| `VALIDATOR_KEY_1` `VALIDATOR_KEY_2` `VALIDATOR_KEY_3` | validator keys; also used to simulate mint collusion after `/sign` refuses |
| `SIGNER` `VALIDATOR_2` `VALIDATOR_3` | addresses, derived if omitted |
| `THRESHOLD` | default `2` |
| `CHALLENGE_WINDOW` | seconds, demo default `120`, deploy-script default `3600` if unset. `0` finalizes inside mint. Max 30 days |
| `RESPONSE_WINDOW` | seconds validators have to sign. Demo default `3600`. Must be non-zero. Max 30 days |
| `CHALLENGE_BOND` `OPERATOR_BOND` `PROTOCOL_REWARD` | wei |
| `POOL_FUND` | wei the deployer deposits into the reward pool at deploy |
| `TREASURY` | rejected-bond recipient, default owner |
| `GAS_PRICE` | wei, default `1000000000` |
| `AXV_ALLOW_TEST_GRADE` | `1` in the demo, unset in production |
| `RECHECK` | `0` in the demo, `1` when forge must re-grade |
| `AXVIGIL_CHALLENGE_ENV` | optional env file to source |
| `VERIFYING_CONTRACT` | collectible, for `/sign` |
| `CHALLENGE_CONTRACT` | challenge book, for `/challenge` |

## Cost

Measured with `./scripts/run_challenge_demo.sh` at 1 gwei legacy (the script's JSON `gasCostTbnb` is the play path only):

| Step | Gas | tBNB at 1 gwei |
|---|---:|---:|
| `DeployChallenge` (registry, skill, collectible, book, validators, seed) | 11,180,204 | 0.0112 |
| Both paths: two mints, challenge, resolve, finalize, two withdraws | about 1.54M (the script prints the exact `gasUsed`) | 0.0015 |
| **Gas total** | **about 12.7M** | **0.013** |

Bonds sit on top of that and mostly move rather than burn. The operator escrows 0.002 tBNB twice. The bad escrow is paid to the challenger. The challenger's 0.001 tBNB bond comes back on an upheld verdict. The honest escrow comes back on `finalize`. If one wallet funds both keys, the slash is an internal transfer. Send **0.05 tBNB** to the deployer and **0.01 tBNB** to the challenger so gas and bonds clear with margin. A 120-second window on BSC also waits that long plus about 20 seconds; an hour-long window costs the same gas and an hour of waiting. Anvil skips the wait with `anvil_increaseTime`.

## Security caveats

- This is a hackathon testnet mechanism. It is not audited. Do not put mainnet funds in it.
- The verdict is only as honest as `threshold` validators. Two colluding graders can uphold a good record or reject a bad one. The window does not remove that assumption; it gives everyone time to ask the same graders to look again, in public.
- `AXV_ALLOW_TEST_GRADE` and `RECHECK=0` will sign whatever the flag says. Production validators must leave the test flag unset and `RECHECK` on.
- An open challenge blocks `finalize` until it is resolved or expired. After expiry the bond comes back, so a griefer's cost is gas, repeated until `readyAt`, plus at most one `responseWindow` after the last challenge. Set a real `challengeBond` if you want rejected (not expired) challenges to cost money. Rejected bonds go to `treasury`.
- The owner can `reclaimPool` and can change windows, bonds, and the treasury. They cannot pull operator escrows or open challenge bonds through that function. They also cannot shorten a window that has already been snapshotted.
- `maxDifficulty`, per-difficulty counts, and `classMask` are dynamically recomputed when a solve is slashed via `revokeSolve`. Admin `revoke` on the skill still wipes the record and blocks new solves.
- Flagged collectibles remain transferable. Buyers have to read `flagged` / `status`. The skill token stays soulbound (`locked` stays true) and simply stops counting as valid when no confirmed solve remains.
- Challenge resolution reads the validator set at verdict time. A validator removed before `resolveChallenge` can no longer count.
- The owner of the collectible chooses the book once, before mint. A malicious book would be trusted with the operator bond. Deploy the book from `DeployChallenge` and check the logged addresses.
