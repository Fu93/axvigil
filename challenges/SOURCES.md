# Provenance and licence review

All three fixtures are newly authored MIT teaching contracts. No upstream Solidity, tests,
reference patches or attack code are copied. The links are historical class context,
not a claim that these small contracts reproduce the original incident.

| Fixture | Historical context | Adaptation boundary |
|---|---|---|
| Reentrant reserve | [BurgerSwap, May 2021](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2021-05/BurgerSwap_exp.sol) | Simple native-asset CEI exercise, not the original multi-hop AMM |
| Spot-price credit | [PancakeBunny, May 2021](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2021-05/PancakeBunny_exp.sol) | Toy manipulable quote versus trusted quote, not a production oracle design |
| Unprotected treasury | [Poly Network, August 2021](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2021-08/PolyNetwork_exp.sol) | Direct missing owner guard, not the original cross-chain authorization bypass |

DeFiHackLabs is used only as a bibliography (repository licence: Apache-2.0; individual
files may have different headers). Future imported tasks require file-level licence and
attribution review. These fixtures use only local synthetic funds; no public-chain RPC.

Variants change names, numeric parameters and a seed-derived constant. Source hashes prevent
exact duplicate issuance. Structural/AST/bytecode deduplication and Muse difficulty calibration
are **not implemented**; these are related exercises, not 60 structurally novel exploits.
