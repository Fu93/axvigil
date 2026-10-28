# PRD v1.2 delivery status

This is a local hackathon prototype built on the repository's pre-existing contracts.
It is not a claim that every PRD P0 requirement is production-ready.

| PRD area | Delivered | Remaining |
|---|---|---|
| Identity | EIP-712 login, single-use nonce, session expiry, live owner checks, tokenId quota | Verify production SPACE ID behavior and eligibility policy |
| Challenges | Three original synthetic fixtures, per-issuance reference check, source hash uniqueness | Historical BSC fork replay, deeper structural mutation, AST/bytecode similarity, Muse pass-rate calibration |
| Grading | Original PoC, patched PoC, 24 functional cases, gas ceiling, limited patch size | Broader property coverage, adversarial review, formal isolation assessment |
| Isolation | Docker offline worker, non-root, read-only root, tmpfs, CPU/memory/pid/time limits, no signer key | Host-level deployment validation; microVMs before hostile public traffic |
| Operations | One worker, backpressure, persistent request limits, >90% pass-rate breaker after 10 results/15 min | Class-specific adaptive thresholds, near-answer clustering, distributed queue and metrics |
| Credentials | Separate signer process, short-lived auth, chain eligibility recheck | Stronger signer policy isolation and remote attestation of grader results |
| Collection | Existing ERC-721 + locked skill record; signed dual outcome, fixed production tiers and limits | Contract audit, VRF, metadata freeze, record ERC-721 compatibility |
| Rarity | Existing operator commit-reveal, stage pools, draw without replacement | Owner withholding/bias protection, VRF v2.5 mainnet consumer |
| NFT images | Existing skill SVG and collectible metadata URI hooks | Muse Image generation, content storage and submission-specific collectible metadata |
| UI | Real wallet login, challenge, submit, verification, mint receipt, skill counts | Collection gallery, rarity reveal display, richer error recovery |
| Agent | Configurable chat-completions provider adapter, JSON validation, retry, solve/submit CLI | Actual Muse credentials, native API verification, live run and learning curve demonstration |
| Deployment | Local Anvil setup, BSC testnet-only existing deploy script, runbook and CI | Funded testnet deployment and recorded addresses/transactions |
| P1/P2 | Not in this hackathon scope | Leaderboards, external MCP, seasons, community tasks, market |

## Existing contract deviations to review before release

- The collectible can currently transfer **before** sellout. PRD §5.9 proposes waiting until
  all 7,777 have minted. This behavior was present before this implementation; it has not
  silently been changed in an integration PR.
- Rarity staging opens the first high-tier allocation at token #1, as documented by the
  existing contract, rather than waiting until 25%. Four releases at 25/50/75/100% would
  require a different final-draw interpretation. Confirm product semantics before mainnet.
- Constructor supports smaller tier counts for tests. The deployment script selects exactly
  7,777; supply cannot subsequently increase. This is not a universal hardcoded 7,777 check.
- ERC-5192 skill record follows the registry owner, but `balanceOf` reverts and Transfer
  events do not track registry transfers. Integrators must read `ownerOf(agentId)` live.
- Collector artwork is mapped by sequential artId within class/tier, rather than directly
  by the submitted challenge. Production art provenance needs an explicit design change.

Do not market these synthetic variants as faithful reproductions or claim difficulty
calibration / live model success that has not been measured.
