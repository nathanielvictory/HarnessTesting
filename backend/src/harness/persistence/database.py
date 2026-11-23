import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


class Database:
    """Owns the SQLite engine and opens transactional ORM sessions."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.engine = create_engine(
            URL.create("sqlite+pysqlite", database=str(self.path)),
            creator=self._connect,
        )
        self._sessions = sessionmaker(bind=self.engine)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)

    def session(self) -> AbstractContextManager[Session]:
        """Commit on successful exit, roll back on error, and close the session."""
        return self._sessions.begin()

    def close(self) -> None:
        self.engine.dispose()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, autocommit=True, check_same_thread=False)
        connection.executescript("""
            PRAGMA busy_timeout = 5000;
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;
            PRAGMA foreign_keys = ON;
        """).close()
        connection.autocommit = False
        return connection
