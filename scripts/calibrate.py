"""Reference solvability matrix, NOT Muse model/difficulty calibration."""

import argparse
from challenges.generator import generate, reference
from verifier.worker import grade


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--variants", type=int, default=20)
    args = p.parse_args()
    seen = set()
    for v in range(3):
        for seed in range(args.variants):
            c = generate(v, seed)
            assert c.fingerprint not in seen
            seen.add(c.fingerprint)
            patch, poc = reference(c)
            result = grade(dict(vulnClass=v, seed=seed, patch=patch, poc=poc))
            assert result["passed"], result
        print(
            f"Class {v}: {args.variants} unique source variants, reference PoC + patch + functional checks passed.",
            flush=True,
        )


if __name__ == "__main__":
    main()
