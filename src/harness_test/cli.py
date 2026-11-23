"""Local workflow harness for LLM-assisted software development."""

import argparse
from importlib.metadata import version


def main() -> int:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('harness-test')}"
    )
    parser.parse_args()
    parser.print_help()
    return 0
