from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .state import Edge, Graph, Node


@dataclass(frozen=True)
class Outcome:
    """A node result with optional data for its outgoing transition."""

    name: str
    data: dict[str, Any] | None = None
    complete: bool = False


@dataclass(frozen=True)
class NewNode:
    node_type: str
    data: dict[str, Any] | None = None
    branch_ref: str | None = None


@dataclass(frozen=True)
class Step:
    node: Node
    outcome: Outcome
    edge: Edge | None


class GraphStore(Protocol):
    def load(self, work_item_id: int) -> Graph: ...

    def save_step(self, node: Node, edge: Edge | None, *, complete: bool = False) -> None: ...

    def add_successor(self, node: Node, target: NewNode, outcome: Outcome, order: int) -> tuple[Node, Edge]: ...


class Traverser:
    def __init__(
        self,
        store: GraphStore,
        operations: Mapping[str, Callable[[Node], Outcome]],
        next_node: Callable[[Graph, Node, Outcome], int | NewNode | None],
    ) -> None:
        self.store = store
        self.operations = operations
        self.next_node = next_node

    def advance(self, work_item_id: int) -> Step | None:
        graph = self.store.load(work_item_id)
        node = graph.current_node()
        if node is None:
            return None
        return self._advance(graph, node)

    def run(self, work_item_id: int) -> Iterator[Step]:
        """Continue the saved graph until an operation has no next node."""
        graph = self.store.load(work_item_id)
        node = graph.current_node()
        while node is not None:
            step = self._advance(graph, node)
            yield step
            node = graph.node(step.edge.to_node_id) if step.edge is not None else None

    def _advance(self, graph: Graph, node: Node) -> Step:
        operation = self.operations.get(node.node_type)
        if operation is None:
            raise ValueError(f"No operation registered for {node.node_type!r}")
        outcome = operation(node)
        destination = self.next_node(graph, node, outcome)
        if isinstance(destination, NewNode):
            target, edge = self.store.add_successor(node, destination, outcome, graph.next_order(node.id))
            graph.add_transition(target, edge)
            return Step(node, outcome, edge)
        edge = None
        if destination is not None:
            edge = graph.transition(node, destination, outcome.name, outcome.data)
        self.store.save_step(node, edge, complete=outcome.complete)
        return Step(node, outcome, edge)
