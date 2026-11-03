# Real-incident track and invariant grading

This note answers the critique that the challenges are toy contracts and that grading is only a few unit tests. Two things changed.

1. The bank has a **real-incident track**: minimal, offline reproductions of public DeFi exploits whose root cause is a smart-contract bug. They use the same mother format as the rest of the bank (renamed identifiers, distractors, reordered functions) and do not fork mainnet at grade time.
2. Every mother is graded with a fifth deterministic check, **`invariantsHold`**: Foundry fuzz tests and stateful invariant handlers run against the **patched** contract at a pinned seed, run count, and depth. A patch that only special-cases the hidden unit tests fails here.

The on-chain classes stay inside the deployed `NUM_CLASSES = 3` cap. The incident's real category is in `mother.json` → `realWorld`. `track` is `"real-incident"` on the five mothers below.

## How a variant is graded

`passed` is all five of:

| Check | What it measures |
|---|---|
| `pocProvesBug` | the submitted PoC passes on the original contract |
| `pocFailsAfterPatch` | that same PoC fails on the patched contract |
| `hiddenTestsPass` | hidden unit tests pass on the patched contract |
| `patchWithinLimits` | diff size, plus the contract name and required functions, are preserved |
| `invariantsHold` | fuzz + invariant tests pass on the patched contract |

The invariant schedule is fixed in `verifier/axvigil_verifier/invariant_profile.py` so a validator re-grade matches:

| Knob | Value |
|---|---|
| fuzz seed | `0xA11CE` (decimal 659918), passed as `--fuzz-seed` |
| fuzz runs | 2000 |
| invariant runs | 256 |
| invariant depth | 32 |
| `fail_on_revert` | false (a reverting action is discarded; a broken property is not) |

Challenges with no `invariantTests` file (the static `reentrancy-001` mint demo and `reentrancy-vault`) record `invariantApplied: false` and `invariantsHold: true`. They do not gain a new way to fail. Mother renders always include `test/Invariant.t.sol`.

Evidence bundles are **schema version 2**. `checks.invariantsHold` and `invariantProfile` (seed, runs, depth, applied) are part of the canonical JSON, so they are inside the CIDv1. `scripts/verify_evidence.py` re-grades and compares those fields. A version 1 bundle still recomputes: the new fields are compared only when the bundle records them. `scripts/run_validators.py` re-grades with the same grader, so `passed` includes the invariant result. Mint authorization is unchanged: it still signs the same EIP-712 `MintAuth` over `submissionHash`.

## Grade time

One reference grade is the four previous Foundry runs plus the invariant file. Measured on the cloud-agent VM (Foundry 1.8.7, `solc` 0.8.28) by `scripts/bench_invariants.py --count 20`: 180/180 reference solutions passed. Mean time is the full five-check grade, not the invariant file alone.

| Mother | Mean grade | Worst | 20-variant wall |
|---|---|---|---|
| `access-control` | 4.21s | 4.28s | 84.3s |
| `beanstalk-flash-governance` | 4.30s | 4.41s | 86.0s |
| `bridge-phantom-deposit` | 4.58s | 4.75s | 91.6s |
| `empty-market-inflation` | 4.82s | 4.94s | 96.4s |
| `nomad-unproven-message` | 4.51s | 4.68s | 90.3s |
| `platypus-emergency-withdraw` | 4.65s | 4.92s | 93.0s |
| `price-manipulation` | 4.67s | 4.88s | 93.5s |
| `reentrancy` | 4.47s | 4.69s | 89.5s |
| `signature-replay` | 4.77s | 4.94s | 95.5s |

The invariant file itself is about 0.1–0.3s of that (2000 fuzz runs and 256×32 invariant calls on these contracts). The rest is compiling the PoC twice and the hidden tests. Reproduce with:

```bash
PATH="$HOME/.foundry/bin:$PATH" python3 scripts/bench_invariants.py
PATH="$HOME/.foundry/bin:$PATH" python3 scripts/bench_invariants.py --count 20
```

`verify-mother --count 20` is the same ship check the bench runs at `--count 20`.

## What the invariant suite catches

Hidden tests are a finite list of calls. Two fixtures in `verifier/tests/test_invariants.py` are patches that pass the other four checks and fail `invariantsHold`:

- **Reentrancy.** Zero the balance before the call only when the amount is `<= 5 ether` (every hidden withdraw and the reference PoC). A 6 ether victim plus an attacker who reenters is outside that list. The reference checks-effects-interactions fix passes; this special case does not.
- **Price manipulation.** Use the reference price only when collateral is exactly 100 (every hidden borrow and the reference PoC) and the spot price otherwise. A deposit of 250, a swap, and a borrow past the reference cap is outside that list.

Both stay inside `maxChangedLines` and keep the public interface. The grader log reports invariant pass counts only. It does not echo invariant or fuzz test names.

## Real-incident mothers

Each source below was checked against the linked post-mortem before it was written into `mother.json`. Loss figures are the ones those write-ups state, not a new estimate. The contracts are minimal reproductions of the vulnerable logic. No protocol source and no DeFiHackLabs test was copied. DeFiHackLabs is MIT; the links are citations.

The class fix is the reference patch in `variantgen/variantgen/fixes.py`. Hidden tests reject narrow patches (for example an emergency withdraw that simply requires zero debt, or a bridge that only blocks one message hash). The invariant file then fuzzes past those cases.

### Already in the bank

| Mother | Incident | Root cause |
|---|---|---|
| `bridge-phantom-deposit` | Qubit QBridge, 27–28 Jan 2022 | a low-level `transferFrom` to an address with no code succeeds, so a deposit that moved nothing is later withdrawn as real coin |
| `empty-market-inflation` | Hundred Finance (Apr 2023) and Sonne (May 2024), Compound-fork empty markets | shares are priced off the live token balance, so a donation inflates the price and rounds a later deposit down |

Sources for those two stay in their `mother.json` files and in [`docs/realbank/README.md`](realbank/README.md).

### `platypus-emergency-withdraw`

| | |
|---|---|
| Incident | Platypus Finance `MasterPlatypusV4.emergencyWithdraw`, Avalanche, 16 Feb 2023, 19:16 UTC |
| Loss | About $8.5M in the primary attack. Omniscia estimated ~$8,529,854 of profit. CertiK reported ~$8.5M. The Platypus team later reported $9.1M across three attacks the same day. |
| Root cause | The solvency check ran **before** the staked LP was reduced, so it still saw the pre-withdraw collateral. The attacker borrowed USP against LP, emergency-withdrew the LP, and left the debt unbacked. The ordinary `withdraw` path checked solvency **after** the update and was not vulnerable in the same way. |
| Class fix | Reduce the stake, then require the position to still be solvent. A partial emergency withdraw that leaves the position solvent must keep working, so `require(debt == 0)` is not the class fix. |
| On-chain class | 2 (access / missing check). Difficulty 1. |

Sources:

- [Omniscia post-mortem](https://medium.com/@omniscia.io/platypus-finance-incident-post-mortem-7b71a0a47a5e)
- [Platypus recovery update](https://medium.com/platypus-finance/update-on-recovery-efforts-after-the-exploitation-a8f64acd5aa5)
- [CertiK analysis](https://www.certik.com/blog/platypus-finance-incident-analysis)
- [DeFiHackLabs `Platypus_exp.sol` (MIT, not copied)](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2023-02/Platypus_exp.sol)

### `nomad-unproven-message`

| | |
|---|---|
| Incident | Nomad Bridge `Replica.process`, Ethereum. Coinbase dates the theft from 1 Aug 2022 21:32 UTC through 2 Aug 2022 05:49 UTC. The vulnerable upgrade landed 21 Jun 2022. |
| Loss | Over $186M in ERC-20s (Coinbase, 9 Aug 2022). BlockSec estimated nearly $200M. |
| Root cause | An unproven message reads as root `bytes32(0)`, because a missing mapping entry is zero. `initialize` had set `confirmAt[bytes32(0)] = 1` when the committed root was zero. `acceptableRoot` therefore returned true, and `process` released funds for a message that was never proven. The previous `Replica` required a non-zero proven status, so the same initialization was safe. |
| Class fix | `acceptableRoot` returns false for the zero root even when the confirm-map says it is acceptable. A message proven under a real root still pays. Replay of a processed message still reverts. |
| On-chain class | 2 (message authentication). Difficulty 2. |

Sources:

- [Nomad root-cause analysis](https://medium.com/nomad-xyz-blog/nomad-bridge-hack-root-cause-analysis-875ad2e5aacd)
- [Coinbase incident analysis](https://www.coinbase.com/blog/nomad-bridge-incident-analysis)
- [BlockSec](https://blocksec.com/blog/how-unchecked-mapping-makes-200-M-losses-of-nomad-bridge)
- [Immunefi hack analysis](https://immunefi.com/blog/bug-fix-reviews/hack-analysis-nomad-bridge-august-2022/)
- [DeFiHackLabs `NomadBridge_exp.sol` (MIT, not copied)](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2022-08/NomadBridge_exp.sol)

### `beanstalk-flash-governance`

| | |
|---|---|
| Incident | Beanstalk Farms governance, Ethereum, 17 Apr 2022, about 12:24 UTC |
| Loss | Beanstalk reported about $77M of non-Bean user assets stolen. Elliptic reported the attacker obtained about $76M (just under 25,000 ETH) and that the protocol lost about $182M in value. Immunefi describes an about $181M incident of which about $77M was non-Bean assets. |
| Root cause | `emergencyCommit` executed a proposal as soon as the caller held at least two-thirds of **live** Stalk. That Stalk could be borrowed and deposited in the same transaction, so a flash loan was enough to pass and execute. Beanstalk's own post says the attacker used a flash loan against the governance process. The BIP's one-day delay had already elapsed before the execution transaction; the delay does not stop a flash loan at execution time, so this model keeps the live-vote bug and does not reproduce the delay. |
| Class fix | Count the checkpoint from the start of the block (`priorVotes`), not votes deposited in the execution transaction. A depositor who already had a supermajority in a previous block can still execute. |
| On-chain class | 2 (governance / missing check). Difficulty 1. |

Sources:

- [Beanstalk governance exploit](https://bean.money/blog/beanstalk-governance-exploit)
- [Immunefi hack analysis](https://immunefi.com/blog/bug-fix-reviews/hack-analysis-beanstalk-governance-attack-april-2022/)
- [Elliptic](https://www.elliptic.co/insights/76-million-stolen-from-beanstalk-farms-defi-stablecoin-protocol/)
- [DeFiHackLabs `Beanstalk_exp.sol` (MIT, not copied)](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2022-04/Beanstalk_exp.sol)

## What still needs a live run

Muse Spark was not called from this change. There is no model API key in the environment, and the task forbids calling one. Someone with `META_API_KEY` should deal the three new mothers in practice mode and confirm the agent loop still terminates:

```bash
# server already running, practice mode picks the mother
# POST /v1/start { "practice": true, "motherId": "platypus-emergency-withdraw" }
# and the same for nomad-unproven-message and beanstalk-flash-governance
```

The offline oracle in `agent/` was not retargeted; it only knows the original reentrancy vault. Reference solutions for the new mothers are the `fixId` functions in `variantgen/variantgen/fixes.py`, and `verify-mother` / `scripts/bench_invariants.py --count 20` is the check that those fixes grade clean.
