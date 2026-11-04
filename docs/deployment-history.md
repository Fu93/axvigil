# BSC testnet deployment history

Superseded deployments, moved out of the README. The current deployment and its addresses are in the [README](../README.md#bsc-testnet-deployment-chain-97) and in [`deployments/bsc-testnet-97.json`](../deployments/bsc-testnet-97.json).

### Previous deployment (PR #4, superseded)

That superseded bytecode never drew Hidden. AxVigilSkill `0xF572376A24467F5a70D0063448e5386BB842cD30`, AxVigilCollectible [`0x7dd86cB7d4e2d7E0b731FB86D53Bd12D02751685`](https://testnet.bscscan.com/address/0x7dd86cB7d4e2d7E0b731FB86D53Bd12D02751685). Its smoke-test token `1` is unrevealed. Full record under `previous` in the manifest. The current rule, live on the current deployment, draws Hidden only from pool 2 at a fixed 0.25%.

### Original deployment (pre-PR #4, superseded)

The first public testnet deployment (now superseded) is below. The deployment uses the demo-only `MockAgentID` registry and a 50 mint-per-hour cap. Its live demo did commit a batch, mint token `1`, and reveal it (details under the table).

| Contract | Address | Explorer |
|---|---|---|
| MockAgentID | `0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e` | [view](https://testnet.bscscan.com/address/0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e) |
| AxVigilSkill | `0xaCd74265DcFc516bD81d9E7173a57ddEdBD3a593` | [view](https://testnet.bscscan.com/address/0xaCd74265DcFc516bD81d9E7173a57ddEdBD3a593) |
| AxVigilCollectible | `0xFDc7744074d49e9049B82A7CCc76824f75f80437` | [view](https://testnet.bscscan.com/address/0xFDc7744074d49e9049B82A7CCc76824f75f80437) |


The collection art plan is documented in [`docs/prd-v1.4-asset-pipeline.md`](prd-v1.4-asset-pipeline.md): Muse Image creates a small Aki source set, while a deterministic local compositor produces the 7,777 final images and metadata. This preserves character consistency, keeps generation cost low and binds the verified vulnerability class to the visual effect.

On that previous deployment, the first live demo completed: verifier `reentrancy-001` passed, Agent ID `1` was created, and Collectible token `1` was minted to the deployer. `AxVigilSkill.totalSolves(1)` was `1` and `currentBatch` was `1`. Those transactions are [commit seed](https://testnet.bscscan.com/tx/0x493ac2cb71504cb643f95c8e1b3a2a7dd53cc33e95428d6cc8297138e100155b), [create Agent ID](https://testnet.bscscan.com/tx/0xc125505638e6562e965977610cbad7a0cfc6f3579c38f3660c24a578a73f5ecd), and [mint collectible](https://testnet.bscscan.com/tx/0xf78ae69add796a107302aaafc178c0b45c4c5936ebcb5ebe47c58f3836b14fce). The reusable script is [`contracts/script/BscLiveDemo.s.sol`](../contracts/script/BscLiveDemo.s.sol); its seed is generated and retained locally, never committed.

That original token `1` was revealed as `REENTRANCY`, tier `COMMON`, with `artId = 0`. The [seed reveal transaction](https://testnet.bscscan.com/tx/0x4a0cb0039cd88c8573cab7bd30a909c2d601036f2607b516dc62abe34f407733) and [token reveal transaction](https://testnet.bscscan.com/tx/0xe17d8f2ea32ee87698bc5367aca087ebb12a841083cd2416111aea525dba6401) are under `previous.previous` in the deployment manifest. The current deployment's token `1` was revealed as tier **COMMON**, artId `20000` (see above).
