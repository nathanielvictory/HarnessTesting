from sqlalchemy import select
from sqlalchemy.orm import Session

from harness.graph.state import Edge, Graph, Node
from harness.graph.traverser import NewNode, Outcome

from ..database import Database
from ..models import Edge as EdgeRecord
from ..models import Node as NodeRecord
from ..models import NodeType, WorkItem, WorkItemStatus


class GraphRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def load(self, work_item_id: int) -> Graph:
        with self.database.session() as session:
            item = session.get(WorkItem, work_item_id)
            if item is None:
                raise LookupError(f"Work item {work_item_id} does not exist")
            edges = session.scalars(
                select(EdgeRecord).join(EdgeRecord.from_node).where(NodeRecord.work_item_id == item.id)
            )
            return Graph(
                item.entry_node_id,
                [_load_node(record) for record in item.nodes],
                [Edge(row.from_node_id, row.to_node_id, row.outbound_order, row.outcome, row.data)
                 for row in edges],
            )

    def add_node(self, work_item_id: int, node_type: str, *, entry: bool = False) -> Node:
        with self.database.session() as session:
            item = session.get(WorkItem, work_item_id)
            if item is None:
                raise LookupError(f"Work item {work_item_id} does not exist")
            if entry and item.entry_node_id is not None:
                raise ValueError(f"Work item {work_item_id} already has an entry node")
            record = NodeRecord(work_item=item, node_type=NodeType(node_type))
            session.add(record)
            if entry:
                item.entry_node = record
            session.flush()
            return _load_node(record)

    def save_step(self, node: Node, edge: Edge | None, *, complete: bool = False) -> None:
        with self.database.session() as session:
            record = _save_node(session, node)
            if edge is not None:
                target = session.get(NodeRecord, edge.to_node_id)
                if edge.from_node_id != node.id or target is None or target.work_item_id != record.work_item_id:
                    raise ValueError("A transition must leave the saved node and stay in its work item")
                _save_edge(session, edge)
            if complete:
                record.work_item.status = WorkItemStatus.COMPLETE

    def add_successor(self, node: Node, target: NewNode, outcome: Outcome, order: int) -> tuple[Node, Edge]:
        with self.database.session() as session:
            source = _save_node(session, node)
            record = NodeRecord(work_item_id=source.work_item_id, node_type=NodeType(target.node_type), data=target.data)
            session.add(record)
            session.flush()
            edge = Edge(source.id, record.id, order, outcome.name, outcome.data)
            _save_edge(session, edge)
            return _load_node(record), edge


def _save_node(session: Session, node: Node) -> NodeRecord:
    record = session.get(NodeRecord, node.id)
    if record is None:
        raise LookupError(f"Node {node.id} does not exist")
    record.model = node.model
    record.conversation = node.conversation
    record.branch_ref = node.branch_ref
    record.commit_sha = node.commit_sha
    record.data = node.data
    return record


def _save_edge(session: Session, edge: Edge) -> None:
    session.add(EdgeRecord(
        from_node_id=edge.from_node_id,
        to_node_id=edge.to_node_id,
        outbound_order=edge.outbound_order,
        outcome=edge.outcome,
        data=edge.data,
    ))


def _load_node(record: NodeRecord) -> Node:
    return Node(
        id=record.id,
        node_type=record.node_type.value,
        model=record.model,
        conversation=record.conversation,
        branch_ref=record.branch_ref,
        commit_sha=record.commit_sha,
        data=record.data,
    )
