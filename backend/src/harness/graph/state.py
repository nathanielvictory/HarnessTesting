from dataclasses import dataclass
from typing import Any


@dataclass
class Node:
    id: int
    action: str
    model: str | None = None
    conversation: dict[str, Any] | None = None
    branch_ref: str | None = None
    commit_sha: str | None = None
    data: dict[str, Any] | None = None


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
        self._outgoing: dict[int, list[Edge]] = {node.id: [] for node in nodes}
        for edge in sorted(edges, key=lambda edge: edge.outbound_order):
            self.node(edge.to_node_id)
            self.node(edge.from_node_id)
            self._outgoing[edge.from_node_id].append(edge)

    def node(self, node_id: int) -> Node:
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} is outside this graph")
        return self.nodes[node_id]

    def history(self) -> tuple[Edge, ...]:
        """Follow recorded transitions from the entry, consuming each edge once."""
        node_id = self.entry_node_id
        history: list[Edge] = []
        departures: dict[int, int] = {}
        while node_id is not None:
            self.node(node_id)
            edges = self._outgoing[node_id]
            index = departures.get(node_id, 0)
            if index == len(edges):
                break
            departures[node_id] = index + 1
            edge = edges[index]
            history.append(edge)
            node_id = edge.to_node_id
        return tuple(history)

    def current_node(self) -> Node | None:
        history = self.history()
        node_id = history[-1].to_node_id if history else self.entry_node_id
        return self.node(node_id) if node_id is not None else None

    def transition(
        self, source: Node, target_id: int, outcome: str, data: dict[str, Any] | None
    ) -> Edge:
        self.node(target_id)
        edge = Edge(source.id, target_id, self.next_order(source.id), outcome, data)
        self._outgoing[source.id].append(edge)
        return edge

    def next_order(self, node_id: int) -> int:
        edges = self._outgoing[node_id]
        return edges[-1].outbound_order + 1 if edges else 1

    def add_transition(self, new_node: Node, edge: Edge) -> None:
        self.nodes[new_node.id] = new_node
        self._outgoing[new_node.id] = []
        self._outgoing[edge.from_node_id].append(edge)
