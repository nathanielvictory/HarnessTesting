from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from harness.graph.state import Edge, Graph, Node
from harness.graph.traverser import NewNode

from ..database import Database
from ..models import Edge as EdgeRecord
from ..models import Node as NodeRecord
from ..models import NodeType, WorkItem, WorkItemStatus

T = TypeVar('T')


class GraphEdit:
    def __init__(self, session: Session, item: WorkItem, graph: Graph) -> None:
        self.session = session
        self.item = item
        self.graph = graph

    def add(self, target: NewNode) -> Node:
        record = NodeRecord(work_item=self.item, node_type=NodeType(target.node_type))
        self.session.add(record)
        self.session.flush()
        node = Node(record.id, target.node_type, conversation=target.conversation,
                    branch_ref=target.branch_ref, commit_sha=target.commit_sha, data=target.data)
        node.update_workflow(status='pending')
        self.graph.nodes[node.id] = node
        return node

    def transition(self, source: Node, target: Node, outcome: str, data: dict | None = None) -> Edge:
        edge = self.graph.record_transition(source.id, target.id, outcome, data)
        self.session.add(EdgeRecord(
            from_node_id=edge.from_node_id, to_node_id=edge.to_node_id,
            outbound_order=edge.outbound_order, outcome=edge.outcome, data=edge.data,
        ))
        return edge

    def finish(self, result: str) -> None:
        if not self.graph.can_complete() or self.graph.entry_node_id is None or not result:
            raise ValueError('Required work is unresolved or has no integrated result.')
        self.graph.node(self.graph.entry_node_id).update_workflow(result_commit=result)
        self.item.status = WorkItemStatus.COMPLETE


class GraphRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def load(self, work_item_id: int) -> Graph:
        with self.database.session() as session:
            return _load_graph(session, _item(session, work_item_id))

    def edit(self, work_item_id: int, change: Callable[[GraphEdit], T]) -> T:
        """Persist the entire graph change or none of it, including new nodes and edges."""
        with self.database.session() as session:
            # Acquire SQLite's writer lock before taking the graph snapshot. Agent
            # turns happen outside this transaction and can record usage independently.
            session.execute(update(WorkItem).where(WorkItem.id == work_item_id).values(id=WorkItem.id))
            item = _item(session, work_item_id)
            if item.status is WorkItemStatus.COMPLETE:
                raise ValueError('This work item is complete.')
            graph = _load_graph(session, item)
            result = change(GraphEdit(session, item, graph))
            graph.validate_dependencies()
            for node in graph.nodes.values():
                record = session.get(NodeRecord, node.id)
                record.model = node.model
                record.conversation = node.conversation
                record.branch_ref = node.branch_ref
                record.commit_sha = node.commit_sha
                record.data = node.data
            return result


def _item(session: Session, item_id: int) -> WorkItem:
    item = session.get(WorkItem, item_id)
    if item is None:
        raise LookupError(f'Work item {item_id} does not exist')
    return item


def _load_graph(session: Session, item: WorkItem) -> Graph:
    edges = session.scalars(select(EdgeRecord).join(EdgeRecord.from_node)
                            .where(NodeRecord.work_item_id == item.id).order_by(EdgeRecord.id))
    return Graph(
        item.entry_node_id,
        [Node(row.id, row.node_type.value, row.model, row.conversation, row.branch_ref, row.commit_sha, row.data)
         for row in item.nodes],
        [Edge(row.from_node_id, row.to_node_id, row.outbound_order, row.outcome, row.data) for row in edges],
    )
