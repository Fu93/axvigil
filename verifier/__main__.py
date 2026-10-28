import argparse
import json
from pathlib import Path
from verifier.runner import run


def main():
    p = argparse.ArgumentParser(
        description="Grade one AxVigil submission in a disposable offline container"
    )
    p.add_argument("command", choices=["grade"])
    p.add_argument("submission", type=Path)
    args = p.parse_args()
    print(json.dumps(run(json.loads(args.submission.read_text())), indent=2))


if __name__ == "__main__":
    main()
