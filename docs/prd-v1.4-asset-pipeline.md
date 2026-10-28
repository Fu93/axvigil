# AxVigil PRD v1.4 — Aki deterministic asset pipeline

## Decision

AxVigil will use Aki as the collection's recurring original character. Muse Image is used for a small, curated source-art set. A local deterministic compositor then combines those layers into the complete 7,777-token collection. The collection is not generated as 7,777 independent AI images.

This keeps Aki visually consistent, makes the collection reproducible, keeps generation cost close to zero after the source set is approved, and preserves the product story: an AI agent's verified vulnerability fix selects the visual trait that appears on its collectible.

## Product story

Aki is AxVigil's cyber-security field agent. Each successful verified challenge leaves an on-chain skill record and mints an Aki collectible. The challenge's `vulnClass`, `difficulty`, `pool`, and the contract's revealed `tier` determine which visual layers are composed. The verifier result is bound to the NFT through `submissionHash`.

The image is therefore a visual rendering of an actual verified solve, not a random profile-picture variation.

## On-chain mapping

The contract remains the source of truth for ownership, rarity and challenge attributes:

- `vulnClass`: `0 REENTRANCY`, `1 PRICE_MANIPULATION`, `2 ACCESS_CONTROL`.
- `difficulty`: `0 BASIC`, `1 ADVANCED`, `2 LEGENDARY`.
- `pool`: `0 NORMAL`, `1 PREMIUM`.
- `tier`: contract-drawn `COMMON`, `RARE`, `EPIC`, `LEGENDARY`, or `HIDDEN`.
- `artId`: assigned during reveal in token order and used to select the final metadata/image.
- `submissionHash`: canonical verifier result hash recorded in the `Minted` event and metadata.

The current contract's art ID formula is:

```text
artId = tier * 100000 + vulnClass * 10000 + index
```

The compositor must generate the final image and metadata for every minted `artId`. It must not infer rarity from an image or overwrite the tier selected by the contract.

## Source asset budget

The first collection pass targets approximately 50 Muse Image source assets. The exact count may change after visual QA, but the source set should cover these roles:

- 6 Aki character/base poses with the same face, pink-lilac hair, cyan streaks, violet-blue eyes, and black cyber-security uniform.
- 8 backgrounds with a shared dark futuristic visual language.
- 9 vulnerability effects: three variants each for reentrancy loops, price manipulation graphs, and access-control barriers.
- 10 tier treatments: two treatments for each rarity tier.
- 8 accessories and handheld/holographic UI elements.
- 5 frame, aura or particle overlays.
- 4 fallback assets for transparent-edge repair, neutral lighting and safe composition.

Muse Image is used to create and refine these source assets, not to place exact metadata text inside the images. Final images should contain no words, token IDs, wallet addresses or submission hashes.

## Layer contract

Every compositing layer must use the same square canvas and coordinate system. The recommended first canvas is 1024×1024 PNG. Each source asset has a manifest entry:

```json
{
  "id": "effect.reentrancy.loop.01",
  "role": "class_effect",
  "vulnClasses": [0],
  "tiers": [0, 1, 2, 3, 4],
  "rarityWeight": 1,
  "file": "layers/effects/reentrancy-loop-01.png",
  "sha256": "..."
}
```

Recommended composition order:

```text
background
→ aura / atmosphere
→ Aki body and base outfit
→ hair and cyan streaks
→ vulnerability class effect
→ difficulty or pool accessory
→ tier frame / rarity treatment
→ particles and final overlay
```

The compositor must use deterministic ordering, deterministic asset selection, fixed transforms and a recorded random seed. A rerun with the same layer manifest and seed must produce byte-identical output or an explicitly documented canonical re-encoding.

## Trait selection rules

The verified vulnerability class controls the semantic focal point:

- `REENTRANCY`: recursive cyan loops, callback traces, circular lock motifs.
- `PRICE_MANIPULATION`: holographic market graph, corrupted price spikes, oracle distortion.
- `ACCESS_CONTROL`: cryptographic key, permission barriers, role-gate geometry.

Difficulty and pool affect secondary treatment rather than changing Aki's identity:

- `BASIC`: restrained pose and simple UI.
- `ADVANCED`: stronger action pose and more active diagnostics.
- `LEGENDARY`: high-energy technical effect and more complex equipment.
- `NORMAL`: standard layer weights.
- `PREMIUM`: stronger accessory and aura variants.

The contract-drawn tier controls the collection rarity treatment:

- `COMMON`: dark uniform, cyan accent, minimal frame.
- `RARE`: blue-violet armor details and expanded holographic panels.
- `EPIC`: purple energy core and stronger class effect.
- `LEGENDARY`: gold-white aura and full equipment treatment.
- `HIDDEN`: unique colorway, pose or accessory combination reserved for four tokens.

## 7,777 output generation

The local generator creates one final image and one metadata JSON for each token output that is needed by the deployment. It does not need 7,777 Muse API calls.

For each final output, the generator records:

```json
{
  "name": "AxVigil Aki #1",
  "description": "Aki's verified Reentrancy solve collectible.",
  "image": "ipfs://<CID>/0.png",
  "attributes": [
    {"trait_type": "Vulnerability", "value": "Reentrancy"},
    {"trait_type": "Difficulty", "value": "Advanced"},
    {"trait_type": "Pool", "value": "Normal"},
    {"trait_type": "Tier", "value": "Common"},
    {"trait_type": "Art ID", "value": 0},
    {"trait_type": "Agent ID", "value": 1},
    {"trait_type": "Submission Hash", "value": "0x..."}
  ]
}
```

The collection generation run must output:

```text
outputs/aki-collection/images/<artId>.png
outputs/aki-collection/metadata/<artId>.json
outputs/aki-collection/layers-manifest.json
outputs/aki-collection/provenance-manifest.json
```

The `images` and `metadata` directories are content-addressed for upload. The final IPFS CID is inserted into `BASE_URI` only after visual QA and manifest hashing.

## Provenance and contract update

Before changing the live contract metadata:

1. Freeze the source-layer manifest.
2. Freeze the compositor version and configuration.
3. Generate the required final outputs.
4. Hash the canonical provenance manifest.
5. Call `setProvenanceHash(bytes32)` once from the contract owner.
6. Upload images and metadata to IPFS.
7. Call `setBaseURI("ipfs://<CID>/", "ipfs://<unrevealed-CID>/unrevealed.json")`.
8. Verify token `1` and a sample from each tier with `tokenURI`, metadata and image links.

`setProvenanceHash` is a one-time commitment. Do not call it until the source layers, generator version and output manifest are frozen.

## Acceptance criteria

The first asset milestone is not 7,777 finished images. It is:

- Aki identity is recognisable across three source samples.
- One sample exists for each vulnerability class.
- One sample exists for each rarity treatment.
- The compositor can generate a deterministic local set.
- Token `1` resolves to a valid image and metadata URI.
- The metadata includes the verifier `submissionHash` and on-chain trait values.
- A rerun produces the same manifest hash.
- No API key, private key, seed, or local wallet data enters Git.

After this milestone passes, generate the complete 7,777 output set locally and upload it to IPFS. The Muse API budget is then limited to source-art generation and targeted revisions rather than collection-scale calls.
