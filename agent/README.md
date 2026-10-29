# AxVigil agent

The autonomous solver. Given a challenge, it reads the vulnerable contract, asks a
model for a patch + a proof-of-concept exploit, grades the answer with the local
verifier, and — if any check fails — feeds the grader log back to the model and
retries. This propose → grade → feed-back → retry loop is the demo's centrepiece.

```bash
# Real run against the Meta Model API:
export META_API_KEY=...            # required
export META_MODEL=muse-spark-1.1   # optional (default)
export META_BASE_URL=https://api.meta.ai/v1   # optional
python -m axvigil_agent solve --challenge ../challenges/reentrancy-vault --max-iters 4

# Offline dry-run of the loop (no key, no network): submits the still-vulnerable
# contract first, then the reference fix, to show the fail -> feedback -> pass path.
python -m axvigil_agent solve --challenge ../challenges/reentrancy-vault --oracle --json
```

`forge` and a Solidity compiler must be reachable (PATH or `FORGE`/`SOLC`). Exit code
is `0` if solved, `1` otherwise.

## What the model is asked for

A single JSON object:

```json
{ "analysis": "...", "patched_contract": "<full target source>", "poc_test": "<full Foundry test>" }
```

The PoC must **pass on the original** contract and **fail on the patch** — a trivial
always-pass test earns nothing, because the verifier scores the differential. The
patch must keep the contract name and public interface and stay within the diff
limits. On failure the retry prompt names exactly which of the four checks failed and
includes the grader log, so the model can self-correct.

## Design

- `model.py` — `ModelClient` interface; `MetaModelClient` (OpenAI-compatible HTTP, stdlib only) and `ScriptedClient` (canned responses for offline tests / the `--oracle` dry-run).
- `prompts.py` — system prompt, first-attempt prompt, and the feedback/retry prompt.
- `solver.py` — the loop: robust JSON extraction, per-iteration grading via the verifier, transcript of every attempt (checks + submissionHash) for the demo video.

The agent never signs anything; a solved run yields the `submissionHash` the backend
will sign into a `MintAuth` (one per passed reward solve, at most two per Agent ID).

## Protocol client

`axvigil_agent.protocol_client.PlatformClient` is a thin reference client for the
platform API — `login` (wallet signature) → `start` → `submit` → `authorize`. It takes
any httpx-compatible client, so the same code works against a running server
(`httpx.Client(base_url=...)`) or an in-process `TestClient`:

```python
from axvigil_agent.protocol_client import PlatformClient
import httpx

c = PlatformClient(httpx.Client(base_url="http://localhost:8000"), PRIVATE_KEY, agent_id=1)
c.login()
ch = c.start(mother_id="reentrancy")
out = c.submit(ch["sessionId"], patch, poc)
if out["passed"]:
    auth = c.authorize(ch["sessionId"], action="mint")  # -> signed MintAuth to submit on-chain
```
