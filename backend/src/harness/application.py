from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Any

from .agents.harness import AgentHarness
from .git.repository import GitRepository
from .graph.state import Graph, Node
from .graph.traverser import Step
from .operations.review import ReviewDecision
from .operations.work_session import WorkSession
from .persistence.catalog import Catalog, ProjectEntry, WorkItemEntry
from .persistence.database import Database
from .persistence.graph.repository import GraphRepository
from .persistence.models import NodeType, WorkItemStatus
from .persistence.usage import UsageRepository, UsageSummary
from .runtime import RuntimeSettings, model_settings


class WorkItemConflict(RuntimeError):
    pass


class Harness:
    """Work-item operations shared by the HTTP API and MCP tools."""

    def __init__(self, database: Database, settings: RuntimeSettings, *, agents: AgentHarness | None = None) -> None:
        self.catalog = Catalog(database)
        self.graphs = GraphRepository(database)
        self.usage = UsageRepository(database)
        self.settings = settings
        self.agents = agents if agents is not None else AgentHarness(
            settings.model, model_settings=model_settings(settings.model), usage=self.usage,
        )
        self._item_locks: dict[int, Lock] = {}
        self._activity: dict[int, tuple[str, list[str]]] = {}
        self._locks_guard = Lock()

    def projects(self) -> list[ProjectEntry]:
        return self.catalog.projects()

    def register_project(self, name: str, repository_path: str) -> ProjectEntry:
        if not name.strip() or not Path(repository_path).is_absolute():
            raise ValueError("Enter a project name and an absolute Git repository path.")
        repository = GitRepository(Path(repository_path))
        return self.catalog.add_project(name.strip(), str(repository.path))

    def work_items(self, project_id: int, status: WorkItemStatus) -> list[WorkItemEntry]:
        self.catalog.get_project(project_id)
        return self.catalog.work_items(project_id, status)

    def project_usage(self, project_id: int) -> UsageSummary:
        self.catalog.get_project(project_id)
        return self.usage.summarize(project_id)

    def work_item_usage(self, item_id: int) -> UsageSummary:
        project, item = self.catalog.get_work_item(item_id)
        return self.usage.summarize(project.id, item_id=item.id)

    def create_work_item(self, project_id: int, title: str | None = None) -> WorkItemEntry:
        project = self.catalog.get_project(project_id)
        title = (title or "").strip() or None
        base = GitRepository(Path(project.repository_path)).commit_sha()
        return self.catalog.add_work_item(project_id, title, base_commit=base)

    def inspect(self, item_id: int) -> dict[str, Any]:
        project, item = self.catalog.get_work_item(item_id)
        graph = self.graphs.load(item_id)
        current = graph.current_node()
        return {
            "project": asdict(project),
            "work_item": asdict(item),
            "entry_node_id": graph.entry_node_id,
            "current_node_id": current.id if current else None,
            "nodes": [_node_view(node) for node in sorted(graph.nodes.values(), key=lambda node: node.id)],
            "transitions": [asdict(edge) for edge in graph.history()],
            "review": _review_view(graph, current),
        }

    def talk(self, item_id: int, message: str) -> dict[str, Any]:
        if not message.strip():
            raise ValueError("Enter a message.")
        return self._advance(item_id, "Preparing a reply", lambda work: work.talk(message.strip()))

    def approve(self, item_id: int) -> dict[str, Any]:
        return self._advance(item_id, "Saving approval", WorkSession.approve)

    def implement(self, item_id: int) -> dict[str, Any]:
        return self._advance(item_id, "Implementing the plan", WorkSession.implement)

    def review(
        self, item_id: int, decision: ReviewDecision, note: str = "", earlier_id: int | None = None,
    ) -> dict[str, Any]:
        if decision in (ReviewDecision.FEEDBACK, ReviewDecision.REVISE) and not note.strip():
            raise ValueError("Describe what should change.")
        return self._advance(
            item_id, "Recording the review", lambda work: work.review(decision, note.strip(), earlier_id=earlier_id)
        )

    def close_work_item(self, item_id: int) -> dict[str, Any]:
        with self._item_operation(item_id, "Closing the work item"):
            self.catalog.complete_work_item(item_id)
            return self.inspect(item_id)

    def activity(self, item_id: int) -> dict[str, Any] | None:
        with self._locks_guard:
            activity = self._activity.get(item_id)
            if activity is None:
                return None
            label, tools = activity
            return {"label": label, "tools": tools.copy()}

    def repository_file(self, item_id: int, node_id: int, path: str) -> str:
        project, _ = self.catalog.get_work_item(item_id)
        graph = self.graphs.load(item_id)
        node = graph.nodes.get(node_id)
        if node is None:
            raise LookupError("That step does not belong to this work item.")
        revision = node.commit_sha or (node.data or {}).get("base_commit")
        if revision is None and node.node_type == NodeType.GOAL_ALIGNMENT:
            revision = next((
                (graph.node(edge.to_node_id).data or {}).get("base_commit")
                for edge in graph.history() if edge.from_node_id == node.id and edge.outcome == "approved"
            ), None)
        if revision is None:
            raise LookupError("This step has no saved repository snapshot.")
        return GitRepository(Path(project.repository_path)).read_text_file(revision, path)

    @contextmanager
    def _item_operation(self, item_id: int, label: str):
        with self._locks_guard:
            if item_id not in self._item_locks:
                self._item_locks[item_id] = Lock()
            lock = self._item_locks[item_id]
            if not lock.acquire(blocking=False):
                raise WorkItemConflict("This work item is already running an operation.")
            tools: list[str] = []
            self._activity[item_id] = (label, tools)

        def report(tool: str) -> None:
            with self._locks_guard:
                tools.append(tool)
                del tools[:-6]

        try:
            yield report
        finally:
            with self._locks_guard:
                del self._activity[item_id]
                lock.release()

    def _advance(self, item_id: int, label: str, operation: Callable[[WorkSession], Step]) -> dict[str, Any]:
        with self._item_operation(item_id, label) as progress:
            project, item = self.catalog.get_work_item(item_id)
            if item.status is WorkItemStatus.COMPLETE:
                raise WorkItemConflict("This work item is complete.")
            work = WorkSession(
                item.id, self.graphs, GitRepository(Path(project.repository_path)), self.agents,
                self.settings.state_dir / "worktrees", item.title, progress=progress,
            )
            operation(work)
            return self.inspect(item_id)


def _node_view(node: Node) -> dict[str, Any]:
    messages = []
    for message in (node.conversation or {}).get("messages", []):
        for part in message.get("parts", []):
            kind, content = part.get("part_kind"), part.get("content")
            if kind in ("user-prompt", "text") and isinstance(content, str):
                messages.append({"role": "user" if kind == "user-prompt" else "assistant", "text": content})
    return {
        "id": node.id, "node_type": node.node_type, "model": node.model,
        "branch_ref": node.branch_ref, "commit_sha": node.commit_sha,
        "data": node.data, "messages": messages,
    }


def _review_view(graph: Graph, node: Node | None) -> dict[str, Any] | None:
    if node is None or node.node_type != NodeType.HUMAN_REVIEW:
        return None
    data = node.data or {}
    target = graph.node(data["target_id"])
    earlier = []
    if target.node_type == NodeType.IMPLEMENTATION:
        plan = graph.node((target.data or {})["plan_id"])
        goal = graph.node((plan.data or {})["goal_id"])
        earlier = [plan.id, goal.id]
    return {"target_id": target.id, "earlier_ids": earlier, "return_review_id": data.get("return_review_id")}
