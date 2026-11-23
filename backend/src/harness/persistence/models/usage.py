from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ModelUsage(Base):
    """Usage reported by Pydantic AI for one accounted model response."""

    __tablename__ = "model_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), index=True)
    run_id: Mapped[str | None]
    recorded_at: Mapped[datetime]
    provider: Mapped[str]
    model: Mapped[str | None]
    input_tokens: Mapped[int]
    cached_input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    unmeasured_requests: Mapped[int]
    priced: Mapped[bool]
    estimated_api_nanodollars: Mapped[int | None]
