"""Local workflow harness for LLM-assisted software development."""

import argparse
import sqlite3
import sys
from importlib.metadata import version


def main() -> int:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('harness')}"
    )
    parser.parse_args()
    from sqlalchemy.exc import SQLAlchemyError

    from harness.persistence.database import Database
    from harness.runtime import RuntimeSettings

    from .app import Application
    from .terminal import Quit, Terminal

    settings = RuntimeSettings.from_environment()
    database = Database(settings.state_dir / "harness.sqlite3")
    try:
        database.initialize()
        Application(database, settings.state_dir, settings.model, Terminal()).run()
    except (Quit, KeyboardInterrupt):
        print("\nHarness closed. Saved work can be reopened from the project menu.")
    except (OSError, sqlite3.Error, SQLAlchemyError) as exc:
        print(f"harness: {exc}", file=sys.stderr)
        return 1
    finally:
        database.close()
    return 0
