from dataclasses import dataclass
from typing import Any


@dataclass
class Node:
    id: int
    node_type: str
    model: str | None = None
    conversation: dict[str, Any] | None = None
    branch_ref: str | None = None
    commit_sha: str | None = None
    data: dict[str, Any] | None = None

    @property
    def workflow(self) -> dict:
        return (self.data or {}).get('_workflow', {})

    def update_workflow(self, **fields: Any) -> None:
        self.data = {**(self.data or {}), '_workflow': {**self.workflow, **fields}}

    @property
    def status(self) -> str:
        return self.workflow.get('status', 'pending')


@dataclass(frozen=True)
class Edge:
    from_node_id: int
    to_node_id: int
    outbound_order: int
    outcome: str
    data: dict[str, Any] | None = None


class Graph:
    def __init__(self, entry_node_id: int | None, nodes: list[Node], edges: list[Edge]):
        self.entry_node_id = entry_node_id
        self.nodes = {node.id: node for node in nodes}
        self._history = tuple(edges)
        for edge in edges:
            self.node(edge.from_node_id)
            self.node(edge.to_node_id)
        if entry_node_id is not None and not any('_workflow' in (node.data or {}) for node in nodes):
            self._restore_linear_item()

    def _restore_linear_item(self) -> None:
        # Old items recorded only a transition walk. Replay its lifecycle once;
        # the repository persists this metadata with the next graph mutation.
        active = self.entry_node_id
        for edge in self._history:
            source = self.node(edge.from_node_id)
            source.update_workflow(status='done')
            target = self.node(edge.to_node_id)
            target.update_workflow(status='pending')
            if edge.outcome in ('approved', 'review', 'review_earlier'):
                target.update_workflow(after=[source.id])
            if edge.outcome == 'revise':
                previous = (source.data or {}).get('target_id')
                if previous in self.nodes:
                    # A legacy revision abandoned the previous tail. Keep it
                    # inspectable, but don't treat it as part of the new path.
                    abandoned = {previous}
                    if self.node(previous).node_type == 'implementation':
                        abandoned.add((self.node(previous).data or {}).get('plan_id'))
                    for old in sorted(self.nodes.values(), key=lambda candidate: candidate.id):
                        if old.id < target.id and (old.id in abandoned or abandoned.intersection(old.workflow.get('after', []))):
                            abandoned.add(old.id)
                            old.update_workflow(status='superseded')
                if goal := (target.data or {}).get('goal_id'):
                    target.update_workflow(after=[goal])
            active = target.id
        if active is not None:
            node = self.node(active)
            decision = (node.data or {}).get('last_decision', {})
            accepted = decision.get('action') == 'accept'
            node.update_workflow(status='done' if accepted else 'pending')
            if accepted and decision.get('reviewed_commit_sha'):
                commit = decision['reviewed_commit_sha']
                node.update_workflow(accepted_commit=commit)
                self.node(self.entry_node_id).update_workflow(result_commit=commit)

    def node(self, node_id: int) -> Node:
        if node_id not in self.nodes:
            raise ValueError(f'Node {node_id} is outside this graph')
        return self.nodes[node_id]

    def history(self) -> tuple[Edge, ...]:
        return self._history

    def scope(self, node: Node) -> int:
        return node.workflow.get('scope', self.entry_node_id or node.id)

    def scopes(self) -> dict[int, list[Node]]:
        groups: dict[int, list[Node]] = {}
        for node in self.nodes.values():
            if node.status != 'superseded':
                groups.setdefault(self.scope(node), []).append(node)
        return groups

    def blockers(self, node: Node) -> list[dict[str, Any]]:
        return [
            {'node_id': key, 'reason': 'Step must succeed'}
            for key in node.workflow.get('after', []) if self.node(key).status != 'done'
        ] + [
            {'node_id': key, 'reason': 'Scoped work must be accepted'}
            for key in node.workflow.get('requires', []) if not self.scope_accepted(key)
        ]

    def scope_accepted(self, scope: int) -> bool:
        members = self.scopes().get(scope, [])
        return bool(members) and all(node.status == 'done' for node in members) and any(
            node.workflow.get('accepted_commit') or (
                node.workflow.get('split') and all(self.scope_accepted(child) for child in node.workflow['split'])
            ) for node in members
        )

    def can_complete(self) -> bool:
        scopes = self.scopes()
        return bool(scopes) and all(self.scope_accepted(key) for key in scopes)

    def current_nodes(self) -> list[Node]:
        return sorted(
            (node for node in self.nodes.values() if node.status == 'pending' and not self.blockers(node)),
            key=lambda node: node.id, reverse=True,
        )

    def select(self, node_id: int | None = None) -> Node | None:
        ready = self.current_nodes()
        if node_id is None:
            return ready[0] if ready else None
        for node in ready:
            if node.id == node_id:
                return node
        raise ValueError(f'Node {node_id} is not ready.')

    def record_transition(self, source: int, target: int, outcome: str, data: dict | None) -> Edge:
        self.node(source)
        self.node(target)
        edge = Edge(source, target, self.next_order(source), outcome, data)
        self._history += (edge,)
        return edge

    def next_order(self, node_id: int) -> int:
        return 1 + max((edge.outbound_order for edge in self._history if edge.from_node_id == node_id), default=0)

    def validate_dependencies(self) -> None:
        """Check both kinds of prerequisites; transition history is not a DAG."""
        from graphlib import CycleError, TopologicalSorter

        sorter = TopologicalSorter()
        scopes = self.scopes()
        for key, members in scopes.items():
            sorter.add(('scope', key), *(('node', node.id) for node in members),
                       *(('scope', child) for node in members for child in node.workflow.get('split', [])))
        for node in self.nodes.values():
            if node.status == 'superseded':
                continue
            after = node.workflow.get('after', [])
            if any(self.node(key).status == 'superseded' for key in after):
                raise ValueError('A prerequisite points to a superseded step.')
            required = node.workflow.get('requires', [])
            if any(key not in scopes for key in required + node.workflow.get('split', [])):
                raise ValueError('A prerequisite points to a missing scope.')
            sorter.add(('node', node.id), *(('node', key) for key in after),
                       *(('scope', key) for key in required))
        try:
            sorter.prepare()
        except CycleError as exc:
            raise ValueError('Work prerequisites cannot contain a cycle.') from exc
