from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .work_item import WorkItem


class Project(Base):
    """Groups work items for a registered repository."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    repository_path: Mapped[str]

    work_items: Mapped[list[WorkItem]] = relationship(back_populates="project")
