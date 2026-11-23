from dataclasses import dataclass

from sqlalchemy import select

from .database import Database
from .models import Node, NodeAction, Project, WorkItem, WorkItemStatus


@dataclass(frozen=True)
class ProjectEntry:
    id: int
    name: str
    repository_path: str


@dataclass(frozen=True)
class WorkItemEntry:
    id: int
    title: str | None
    status: WorkItemStatus


class Catalog:
    def __init__(self, database: Database) -> None:
        self.database = database

    def projects(self) -> list[ProjectEntry]:
        with self.database.session() as session:
            rows = session.scalars(select(Project).order_by(Project.name, Project.id))
            return [ProjectEntry(row.id, row.name, row.repository_path) for row in rows]

    def add_project(self, name: str, repository_path: str) -> ProjectEntry:
        with self.database.session() as session:
            record = Project(name=name, repository_path=repository_path)
            session.add(record)
            session.flush()
            return ProjectEntry(record.id, record.name, record.repository_path)

    def work_items(self, project_id: int, status: WorkItemStatus) -> list[WorkItemEntry]:
        with self.database.session() as session:
            rows = session.scalars(select(WorkItem).where(
                WorkItem.project_id == project_id, WorkItem.status == status
            ).order_by(WorkItem.updated_at.desc(), WorkItem.id.desc()))
            return [WorkItemEntry(row.id, row.title, row.status) for row in rows]

    def get_work_item(self, item_id: int) -> tuple[ProjectEntry, WorkItemEntry]:
        with self.database.session() as session:
            item = session.get(WorkItem, item_id)
            if item is None:
                raise LookupError(f"Work item {item_id} does not exist")
            project = item.project
            return ProjectEntry(project.id, project.name, project.repository_path), WorkItemEntry(
                item.id, item.title, item.status
            )

    def get_project(self, project_id: int) -> ProjectEntry:
        with self.database.session() as session:
            row = session.get(Project, project_id)
            if row is None:
                raise LookupError(f"Project {project_id} does not exist")
            return ProjectEntry(row.id, row.name, row.repository_path)

    def add_work_item(self, project_id: int, title: str | None) -> WorkItemEntry:
        with self.database.session() as session:
            item = WorkItem(project_id=project_id, title=title)
            item.entry_node = Node(work_item=item, action=NodeAction.GOAL_ALIGNMENT)
            session.add(item)
            session.flush()
            return WorkItemEntry(item.id, item.title, item.status)
