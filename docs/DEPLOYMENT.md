# Deployment runbook (testnet only)

1. Run the local tests and offline Docker smoke tests from the root README.
2. Use a fresh BSC testnet deployer funded with faucet tBNB. Generate a separate signer key
   and expose only its **address** to the deploy process. Do not send keys in chat or commit them.
3. Configure the variables documented in `contracts/script/Deploy.s.sol`: `PRIVATE_KEY`,
   `SIGNER`, `BSC_TESTNET_RPC`, optional `OWNER`, `AGENT_REGISTRY`, metadata URIs and `SEED_HASH`.
   Use `MockAgentID` only for testnet. Keep the reveal seed offline and separate from the signer.
4. Dry-run first, review transaction destinations and chain ID, then broadcast:

   ```bash
   cd contracts
   forge script script/Deploy.s.sol --rpc-url bsc_testnet
   forge script script/Deploy.s.sol --rpc-url bsc_testnet --broadcast
   ```

5. Record registry, skill, collectible addresses and the transaction hashes. If ownership
   was handed to another wallet, that wallet must call `acceptOwnership()` on Collectible.
6. Build backend ABI artifacts with `forge build --root contracts`. Copy `.env.example`,
   configure chain 97 and the actual addresses. Run signer and API as separate services.
   Only signer gets `MINT_SIGNER_KEY`. Only API gets Docker access. Neither service should
   run as root. The signer binds loopback/private network only, never an internet route.
7. Use TLS for the public API. The included UI uses same-origin requests. Keep signer and
   Docker daemon inaccessible. Do not run more than one API instance against the SQLite DB:
   the worker semaphore is process-local. Back up the SQLite DB and keep reveal seeds safe.
8. Build the grader locally and execute the smoke tests before enabling submissions.
   Docker images/toolchains are version-tagged; lock image digests for a public deployment.
9. Mint a mock testnet Agent ID to the demo wallet, verify login, draw, submit, authorize,
   actual mint receipt, live skill count, batch reveal and quota/nonce replay rejection.
10. Keep the contract paused if reference checks, ownership checks or grading fail. Never
    bypass the grader or hand-sign authorizations just to make a demo appear to succeed.

No deployment was performed by this implementation. Mainnet requires contract and sandbox
review, VRF, operational hardening and resolution of the status document's product gaps.
