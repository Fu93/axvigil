from challenges.generator import generate, reference
from verifier.runner import run


def main():
    for v in range(3):
        c = generate(v, 100)
        patch, poc = reference(c)
        r = run(dict(vulnClass=v, seed=100, patch=patch, poc=poc))
        assert r["passed"], r
    print(
        "Three reference submissions passed inside offline disposable Docker containers."
    )


if __name__ == "__main__":
    main()
