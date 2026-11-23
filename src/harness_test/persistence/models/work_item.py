from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .node import Node
    from .project import Project


class WorkItem(Base):
    """A unit of project work and the user's entry point into its graph."""

    __tablename__ = "work_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str | None]
    entry_node_id: Mapped[int | None] = mapped_column(ForeignKey("nodes.id"))

    project: Mapped[Project] = relationship(back_populates="work_items")
    nodes: Mapped[list[Node]] = relationship(back_populates="work_item", foreign_keys="Node.work_item_id")
    entry_node: Mapped[Node | None] = relationship(foreign_keys=[entry_node_id], post_update=True)
