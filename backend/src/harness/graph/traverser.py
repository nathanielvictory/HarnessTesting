from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Protocol, TypeVar

from .state import Edge, Graph, Node


@dataclass(frozen=True)
class Outcome:
    name: str
    data: dict[str, Any] | None = None
    complete: bool = False


@dataclass(frozen=True)
class NewNode:
    node_type: str
    data: dict[str, Any] | None = None
    branch_ref: str | None = None
    commit_sha: str | None = None
    conversation: dict[str, Any] | None = None


@dataclass(frozen=True)
class Step:
    node: Node
    outcome: Outcome
    edge: Edge | None


class Edit(Protocol):
    graph: Graph

    def add(self, target: NewNode) -> Node: ...
    def transition(self, source: Node, target: Node, outcome: str, data: dict | None = None) -> Edge: ...
    def finish(self, result: str) -> None: ...


T = TypeVar('T')


class GraphStore(Protocol):
    def load(self, work_item_id: int) -> Graph: ...
    def edit(self, work_item_id: int, change: Callable[[Edit], T]) -> T: ...


class Traverser:
    def __init__(
        self, store: GraphStore, operations: Mapping[str, Callable[[Node], Outcome]],
        apply: Callable[[Edit, Node, Outcome], Edge | None],
        finalize: Callable[[Graph], str] | None = None,
    ) -> None:
        self.store = store
        self.operations = operations
        self.apply = apply
        self.finalize = finalize

    def advance(self, work_item_id: int, node_id: int) -> Step:
        original = self.store.load(work_item_id).select(node_id)
        operation = self.operations.get(original.node_type)
        if operation is None:
            raise ValueError(f'No operation registered for {original.node_type!r}')
        node = deepcopy(original)
        outcome = operation(node)

        def save(edit: Edit) -> Step:
            if edit.graph.select(node.id) != original:
                raise ValueError(f'Node {node.id} changed while running.')
            edit.graph.nodes[node.id] = node
            edge = self.apply(edit, node, outcome)
            complete = outcome.name == 'accept' and edit.graph.can_complete() and self.finalize is not None
            if complete:
                edit.finish(self.finalize(edit.graph))
            return Step(node, replace(outcome, complete=complete), edge)

        return self.store.edit(work_item_id, save)
