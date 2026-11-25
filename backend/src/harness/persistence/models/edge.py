from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .node import Node


class Edge(Base):
    """A recorded transition with an application-assigned order at its source node."""

    __tablename__ = "edges"
    __table_args__ = (
        UniqueConstraint("from_node_id", "outbound_order", name="uq_edges_from_node_outbound_order"),
        CheckConstraint("outbound_order >= 1", name="ck_edges_positive_outbound_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    to_node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), index=True)
    outbound_order: Mapped[int]
    outcome: Mapped[str]
    status: Mapped[str] = mapped_column(server_default='approved')
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))

    from_node: Mapped[Node] = relationship(back_populates="outgoing_edges", foreign_keys=[from_node_id])
    to_node: Mapped[Node] = relationship(back_populates="incoming_edges", foreign_keys=[to_node_id])
