from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .edge import Edge
    from .work_item import WorkItem


class NodeType(StrEnum):
    """Type of step represented by a graph node."""

    GOAL_ALIGNMENT = "goal_alignment"
    TECHNICAL_PLANNING = "technical_planning"
    IMPLEMENTATION = "implementation"
    HUMAN_REVIEW = "human_review"

    AUTOMATED_REVIEW = "automated_review"
    RUN_PYTHON = "run_python"


class Node(Base):
    """The saved state of a node in a work item's graph."""

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_item_id: Mapped[int] = mapped_column(ForeignKey("work_items.id"), index=True)
    # Keep the existing SQLite names so saved graphs reopen without a migration.
    node_type: Mapped[NodeType] = mapped_column(
        "action",
        Enum(
            NodeType,
            name="node_action",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda node_types: [node_type.value for node_type in node_types],
        )
    )
    model: Mapped[str | None]
    conversation: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    branch_ref: Mapped[str | None]
    commit_sha: Mapped[str | None]
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))

    work_item: Mapped[WorkItem] = relationship(back_populates="nodes", foreign_keys=[work_item_id])
    outgoing_edges: Mapped[list[Edge]] = relationship(
        back_populates="from_node", foreign_keys="Edge.from_node_id", order_by="Edge.outbound_order"
    )
    incoming_edges: Mapped[list[Edge]] = relationship(
        back_populates="to_node", foreign_keys="Edge.to_node_id"
    )
