"""Shared metadata for the harness's database models."""

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utc_now() -> datetime:
    # SQLite stores these timestamps without a timezone. The stored values are UTC.
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=_utc_now, onupdate=_utc_now)
