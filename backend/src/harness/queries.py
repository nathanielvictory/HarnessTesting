from dataclasses import asdict
from pathlib import Path
from typing import Any

from .application import ActiveCommands, CommandActivity, WorkItemConflict
from .git.repository import GitRepository
from .graph.node import Node, NodeStatus
from .graph.state import Edge, EdgeStatus, Graph
from .operations.implementation import Implementation
from .operations.review import Review
from .persistence.catalog import Catalog, ProjectEntry, WorkItemEntry
from .persistence.graph.repository import GraphRepository
from .persistence.models import WorkItemStatus
from .persistence.usage import UsageRepository, UsageSummary


class HarnessQueries:
    def __init__(self, catalog: Catalog, graphs: GraphRepository, usage: UsageRepository,
                 active: ActiveCommands) -> None:
        self.catalog = catalog
        self.graphs = graphs
        self.usage = usage
        self.active = active

    def activity(self, item_id: int) -> CommandActivity | None:
        return self.active.snapshot(item_id)

    def projects(self) -> list[ProjectEntry]:
        return self.catalog.projects()

    def work_items(self, project_id: int, status: WorkItemStatus) -> list[WorkItemEntry]:
        self.catalog.get_project(project_id)
        return self.catalog.work_items(project_id, status)

    def project_usage(self, project_id: int) -> UsageSummary:
        self.catalog.get_project(project_id)
        return self.usage.summarize(project_id)

    def work_item_usage(self, item_id: int) -> UsageSummary:
        project, item = self.catalog.get_work_item(item_id)
        return self.usage.summarize(project.id, item_id=item.id)

    def inspect(self, item_id: int) -> dict[str, Any]:
        project, item = self.catalog.get_work_item(item_id)
        graph = self.graphs.load(item_id)
        ready = graph.current_nodes()
        blocked = {}
        for edge in graph.edges:
            if edge.status == EdgeStatus.PENDING and edge.target.status == NodeStatus.PENDING and not graph.is_ready(edge.target):
                blocked.setdefault(edge.to_node_id, []).append({
                    "node_id": edge.from_node_id, "reason": "Incoming edge needs approval",
                })
        return {
            "project": asdict(project),
            "work_item": asdict(item),
            "entry_node_id": graph.entry_node_id,
            "ready_node_ids": [node.id for node in ready],
            "blocked": blocked,
            "nodes": [_node_view(node) for node in sorted(graph.nodes, key=lambda node: node.id)],
            "transitions": [_edge_view(edge) for edge in graph.history()],
            "reviews": {node.id: _review_view(graph, node) for node in ready if isinstance(node, Review)},
        }

    def repository_file(self, item_id: int, node_id: int, path: str) -> str:
        project, _ = self.catalog.get_work_item(item_id)
        graph = self.graphs.load(item_id)
        node = graph.find_node(node_id)
        if node is None:
            raise LookupError("That step does not belong to this work item.")
        revision = node.state.commit_sha or node.state.data.base_commit
        if revision is None:
            raise LookupError("This step has no saved repository snapshot.")
        return GitRepository(Path(project.repository_path)).read_text_file(revision, path)

    def implementation_diff(self, item_id: int, node_id: int) -> dict[str, Any]:
        repository, base, commit = self._implementation_comparison(item_id, node_id)
        files = [
            {"status": change.status, "old_path": change.old_path, "new_path": change.new_path,
             "old_mode": change.old_mode, "new_mode": change.new_mode}
            for change in repository.changed_files(base, commit)
        ]
        return {"base_commit": base, "commit": commit, "files": files}

    def implementation_file_diff(self, item_id: int, node_id: int, file_index: int, commit: str) -> dict[str, str | bool]:
        repository, base, saved_commit = self._implementation_comparison(item_id, node_id)
        if commit != saved_commit:
            raise WorkItemConflict("The saved comparison changed. Reopen the work item to load it.")
        changes = repository.changed_files(base, saved_commit)
        if not 0 <= file_index < len(changes):
            raise LookupError("This file is absent from the saved comparison.")
        return repository.file_diff(changes[file_index])

    def _implementation_comparison(self, item_id: int, node_id: int) -> tuple[GitRepository, str, str]:
        project, _ = self.catalog.get_work_item(item_id)
        graph = self.graphs.load(item_id)
        node = graph.find_node(node_id)
        if node is None:
            raise LookupError("That step does not belong to this work item.")
        implementation = graph.creation_edge(node).source if isinstance(node, Review) else node
        if not isinstance(implementation, Implementation):
            raise LookupError("This step has no implementation to compare.")
        reviewed_commit = node.state.data.reviewed_commit_sha if isinstance(node, Review) else None
        commit = reviewed_commit or implementation.state.commit_sha
        base = implementation.state.data.base_commit
        if not base or not commit:
            raise LookupError("This implementation has no saved comparison yet.")

        return GitRepository(Path(project.repository_path)), base, commit


def _node_view(node: Node) -> dict[str, Any]:
    messages = []
    for message in (node.state.conversation or {}).get("messages", []):
        for part in message.get("parts", []):
            kind, content = part.get("part_kind"), part.get("content")
            if kind in ("user-prompt", "text") and isinstance(content, str):
                messages.append({"role": "user" if kind == "user-prompt" else "assistant", "text": content})
    return {
        "id": node.id, "node_type": node.node_type, "model": node.state.model,
        "branch_ref": node.state.branch_ref, "commit_sha": node.state.commit_sha,
        "data": asdict(node.state.data),
        "messages": messages, "status": node.status.value,
        "conversation_started": node.state.conversation is not None,
    }


def _review_view(graph: Graph, node: Review) -> dict[str, Any]:
    source = graph.creation_edge(node).source
    earlier_ids = [step.id for step in graph.predecessors(source)
                   if step.node_type in ('technical_planning', 'goal_alignment')]
    return {'target_id': source.id, 'earlier_ids': earlier_ids,
            'return_review_id': node.state.data.return_review_id}

def _edge_view(edge: Edge) -> dict[str, Any]:
    return {
        'id': edge.id,
        'from_node_id': edge.from_node_id,
        'to_node_id': edge.to_node_id,
        'outbound_order': edge.outbound_order,
        'outcome': edge.outcome,
        'status': edge.status.value,
        'data': {'note': edge.note} if edge.note else None,
    }
