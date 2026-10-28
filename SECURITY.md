# Security boundaries

This repository intentionally contains vulnerable educational Solidity. Only the exact
synthetic/local exercises and testnet deployments are in scope. Do not scan or attack other
systems. No real funds should be used.

The API treats the patch and PoC as untrusted. It accepts **two source strings**, not an archive,
file paths, tests, Foundry configuration or executable scripts. Imports are rejected; sources
are size-limited; patch changes are capped. Inputs are mounted read-only in a disposable
Docker worker with no network, no capabilities, non-root identity, a read-only root filesystem,
a small tmpfs and CPU/memory/process/wall-clock limits. The only node is local ephemeral Anvil.
The worker has no access to signer keys, API credentials, the Docker socket or production RPC.

PoCs execute as transactions on Anvil, not Forge tests. Foundry cheatcodes are therefore not
available to a malicious attack contract. The trusted evaluator determines victim loss,
unauthorized ownership changes or excess debt independently of the attack's return value.
A pass requires both the original exploit and patched functional checks.

The API accepts only results matching its generated challenge, seed, vulnerability class,
difficulty and canonical source hash, with all verification gates set to boolean true.
Issued reference solutions use the same checks. Backend timing, identity and authorization
fields are never accepted from participant requests. Nonces and task transitions are persisted
with SQLite transactions; mint authorization retries retain the same nonce and deadline.
On-chain quota and hourly limits remain authoritative.

The signer is a separate process and receives only mint fields over an authenticated private
HTTP interface. It rechecks chain eligibility, deadline, ranges and nonce. It **trusts the API's
verification decision**; the service token is an authorization boundary, not a cryptographic
proof of execution. Compromise of the API/token can authorize fraudulent solves, though it
does not expose the signing key to a grader. A hardened deployment needs signed/attested grader
results and an independently enforced signer policy. Do not claim that process separation
alone solves a fully compromised backend.

## Limits

- Docker shares the host kernel; a compiler/kernel escape remains possible. Use dedicated
  disposable hosts or microVMs before accepting adversarial public traffic.
- The included reference-check CLI and pytest tests run only trusted repository fixtures
  locally. There is no server flag for executing arbitrary submissions outside Docker.
- Test logic is open source, so private execution does not make the suite unknowable. Finite
  tests cannot prove arbitrary patches correct. Extend coverage and review grading bypasses.
- Source hashes prevent exact reissuance; they are not AST or semantic plagiarism detection.
- Rate limits are basic persistent counters and worker capacity is process-local. Use a
  trusted reverse proxy and a real distributed queue for public scaling.
- Existing commit-reveal randomness trusts the operator and may stall permanently if a
  seed is withheld. It is not suitable for production fair distribution.
- Existing skill token ERC-721 support is partial; see `contracts/README.md`.
- No automatic public-chain exploit, mainnet deployment or real-fund operation is included.

Report a problem privately to the repository owner through their verified GitHub contact
channel. Do not include live secrets or unrepaired third-party vulnerabilities in public issues.
