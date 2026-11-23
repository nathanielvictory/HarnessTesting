"""Local workflow harness for LLM-assisted software development."""

import argparse
import os
import sqlite3
import sys
from importlib.metadata import version
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('harness-test')}"
    )
    parser.parse_args()
    from sqlalchemy.exc import SQLAlchemyError

    from harness_test.persistence.database import Database

    from .app import Application
    from .terminal import Quit, Terminal

    data_home = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    state_dir = Path(os.environ.get("HARNESS_STATE_DIR") or data_home / "HarnessTest").resolve()
    database = Database(state_dir / "harness.sqlite3")
    try:
        database.initialize()
        model = os.environ.get("HARNESS_MODEL", "openai-codex:gpt-6-luna")
        Application(database, state_dir, model, Terminal()).run()
    except (Quit, KeyboardInterrupt):
        print("\nHarness closed. Saved work can be reopened from the project menu.")
    except (OSError, sqlite3.Error, SQLAlchemyError) as exc:
        print(f"harness: {exc}", file=sys.stderr)
        return 1
    finally:
        database.close()
    return 0
