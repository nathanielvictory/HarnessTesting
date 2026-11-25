from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum

from harness.git.repository import GitWorkspace

from .node import Node, NodeData, NodeState, NodeStatus


class EdgeStatus(StrEnum):
    PENDING = 'pending'
    APPROVED = 'approved'


@dataclass
class Edge:
    source: Node
    target: Node
    outbound_order: int
    outcome: str
    note: str = ''
    status: EdgeStatus = EdgeStatus.PENDING
    id: int | None = None

    @property
    def from_node_id(self) -> int:
        return self.source.id

    @property
    def to_node_id(self) -> int:
        return self.target.id


class Graph:
    def __init__(self, entry_node_id: int | None, workspace: GitWorkspace, *,
                 make_node: Callable[[type[Node], NodeState, Graph], Node],
                 progress: Callable[[str], None] | None = None) -> None:
        self.entry_node_id = entry_node_id
        self.workspace = workspace
        self.progress = progress
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []
        self._make_node = make_node

    def find_node(self, node_id: int) -> Node | None:
        return next((node for node in self.nodes if node.state.id == node_id), None)

    def node(self, node_id: int) -> Node:
        node = self.find_node(node_id)
        if node is None:
            raise LookupError(f'Node {node_id} is outside this graph.')
        return node

    def history(self) -> tuple[Edge, ...]:
        return tuple(self.edges)

    def creation_edge(self, node: Node) -> Edge:
        for edge in self.edges:
            if edge.target is node and edge.outcome != 'rollback':
                return edge
        raise LookupError(f'Node {node.id} has no creation edge.')

    def is_ready(self, node: Node) -> bool:
        return node.status == NodeStatus.PENDING and (
            node.state.id == self.entry_node_id and self.entry_node_id is not None
            or any(edge.target is node and edge.status == EdgeStatus.APPROVED for edge in self.edges)
        )

    def current_nodes(self) -> list[Node]:
        return sorted((node for node in self.nodes if self.is_ready(node)), key=lambda node: node.id, reverse=True)

    def select(self, node_id: int) -> Node:
        node = self.node(node_id)
        if not self.is_ready(node):
            raise ValueError(f'Node {node_id} is not ready.')
        return node

    def connect[D: NodeData](self, source: Node, node_class: type[Node[D]], state: NodeState[D],
                             outcome: str, note: str = '') -> Edge:
        target = self._make_node(node_class, state, self)
        self.nodes.append(target)
        return self.add_edge(source, target, outcome, note)

    def create_nodes[D: NodeData](
        self, source: Node, node_class: type[Node[D]], states: Iterable[NodeState[D]], outcome: str,
    ) -> None:
        """Create nodes with edges from the source, replacing its unapproved destinations."""
        pending = [edge for edge in self.edges if edge.source is source and edge.status == EdgeStatus.PENDING
                   and edge.outcome != 'rollback' and edge.target.status == NodeStatus.PENDING
                   and not self.is_ready(edge.target)]
        for state in states:
            self.connect(source, node_class, state, outcome)

        for edge in pending:
            self.edges.remove(edge)
        for target in {edge.target for edge in pending}:
            if not any(edge.source is target or edge.target is target for edge in self.edges):
                self.nodes.remove(target)

    def add_edge(self, source: Node, target: Node, outcome: str, note: str = '') -> Edge:
        if source not in self.nodes or target not in self.nodes:
            raise ValueError('Both endpoints must belong to this graph.')
        order = 1 + max((edge.outbound_order for edge in self.edges if edge.source is source), default=0)
        edge = Edge(source, target, order, outcome, note)
        self.edges.append(edge)
        return edge

    def predecessors(self, node: Node) -> list[Node]:
        previous: list[Node] = []
        pending = [node]
        seen = {node}
        while pending:
            current = pending.pop(0)
            for edge in reversed(self.edges):
                if (edge.target is current and edge.status == EdgeStatus.APPROVED
                        and edge.outcome != 'rollback' and edge.source not in seen):
                    seen.add(edge.source)
                    previous.append(edge.source)
                    pending.append(edge.source)
        return previous

    def rollback(self, source_id: int, target_id: int, note: str) -> Edge:
        source = self.select(source_id)
        target = self.node(target_id)
        self._check_rollback(source, target)
        return self.add_edge(source, target, 'rollback', note.strip())

    def pending_edge(self, edge_id: int) -> Edge:
        edge = next((edge for edge in self.edges if edge.id == edge_id), None)
        if edge is None:
            raise LookupError(f'Edge {edge_id} is outside this graph.')
        if edge.status == EdgeStatus.APPROVED:
            raise ValueError('This edge has already been approved.')
        return edge

    def approve_edge(self, edge_id: int, data: dict[str, object] | None = None) -> int | None:
        """Approve an edge and return the destination ID if it needs its first turn."""
        edge = self.pending_edge(edge_id)
        if edge.source.status == NodeStatus.SUPERSEDED:
            raise ValueError('The edge leaves a superseded node.')
        if edge.source.status != NodeStatus.DONE and not self.is_ready(edge.source):
            raise ValueError('The source node is not ready.')
        if edge.outcome == 'rollback':
            if data:
                raise ValueError('Node data can only be edited when approving a destination’s first turn.')
            self._check_rollback(edge.source, edge.target)
            self._apply_rollback(edge.target)
        elif edge.target.status != NodeStatus.PENDING:
            raise ValueError('The destination is no longer pending.')
        else:
            if data:
                if edge.target.state.conversation is not None:
                    raise ValueError('The destination has already started its conversation.')
                edge.target.update_data(data)
            edge.source.state.status = NodeStatus.DONE
        edge.status = EdgeStatus.APPROVED
        if edge.outcome != 'rollback' and edge.target.state.conversation is None:
            return edge.target.id
        return None

    def _check_rollback(self, source: Node, target: Node) -> None:
        if target.status != NodeStatus.DONE or target not in self.predecessors(source):
            raise ValueError('Choose a previous node on the path to the current node.')

    def _apply_rollback(self, target: Node) -> None:
        descendants = {target}
        frontier = [target]
        while frontier:
            current = frontier.pop()
            for edge in self.edges:
                if edge.source is current and edge.outcome != 'rollback' and edge.target not in descendants:
                    descendants.add(edge.target)
                    frontier.append(edge.target)
        for node in descendants - {target}:
            node.state.status = NodeStatus.SUPERSEDED
        target.state.status = NodeStatus.PENDING
