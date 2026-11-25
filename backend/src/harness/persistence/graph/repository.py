from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from pydantic import TypeAdapter
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from harness.agents.harness import AgentHarness
from harness.git.repository import GitWorkspace
from harness.graph.node import Node, NodeState, NodeStatus
from harness.graph.state import Edge, EdgeStatus, Graph
from harness.operations.alignment import GoalAlignment
from harness.operations.implementation import Implementation
from harness.operations.planning import TechnicalPlanning
from harness.operations.review import Review

from ..database import Database
from ..models import Edge as EdgeRecord
from ..models import Node as NodeRecord
from ..models import NodeType, WorkItem


NODE_CLASSES: dict[str, type[Node]] = {
    cls.node_type: cls for cls in (GoalAlignment, TechnicalPlanning, Implementation, Review)
}
NODE_DATA = {name: TypeAdapter(cls.data_type) for name, cls in NODE_CLASSES.items()}


class GraphRepository:
    def __init__(self, database: Database, agent: AgentHarness, worktrees: Path) -> None:
        self.database = database
        self.agent = agent
        self.worktrees = worktrees

    def load(self, work_item_id: int, *, progress: Callable[[str], None] | None = None) -> Graph:
        with self.database.session() as session:
            return self._load(session, _item(session, work_item_id), progress)

    def edit[T](self, work_item_id: int, change: Callable[[Graph], T], *,
                progress: Callable[[str], None] | None = None) -> T:
        graph = self.load(work_item_id, progress=progress)
        original = deepcopy(_node_states(graph))
        edge_statuses = _edge_statuses(graph)
        result = change(graph)

        # Model turns run outside the write transaction so they can record usage.
        with self.database.session() as session:
            session.execute(update(WorkItem).where(WorkItem.id == work_item_id).values(id=WorkItem.id))
            item = _item(session, work_item_id)
            current = self._load(session, item)
            if _node_states(current) != original or _edge_statuses(current) != edge_statuses:
                raise ValueError('The graph changed while this command was running.')
            records = {row.id: row for row in item.nodes}
            for node in graph.nodes:
                state = node.state
                record = records.get(state.id)
                if record is None:
                    record = NodeRecord(work_item=item, node_type=NodeType(node.node_type), commit_sha=state.commit_sha)
                    session.add(record)
                record.status = state.status.value
                record.model = state.model
                record.conversation = state.conversation
                record.branch_ref = state.branch_ref
                record.data = asdict(state.data)
                if state.id is None:
                    session.flush()
                    state.id = record.id

            for edge in graph.edges:
                if edge.id is None:
                    session.add(EdgeRecord(
                        from_node_id=edge.from_node_id, to_node_id=edge.to_node_id,
                        outbound_order=edge.outbound_order, outcome=edge.outcome,
                        status=edge.status.value, data={'note': edge.note} if edge.note else None,
                    ))
                elif edge.status != edge_statuses[edge.id]:
                    session.get(EdgeRecord, edge.id).status = edge.status.value

            removed_edges = edge_statuses.keys() - {edge.id for edge in graph.edges}
            removed_nodes = records.keys() - {node.id for node in graph.nodes}
            if removed_edges:
                session.flush()
                session.execute(delete(EdgeRecord).where(EdgeRecord.id.in_(removed_edges)))
            if removed_nodes:
                session.execute(delete(NodeRecord).where(NodeRecord.id.in_(removed_nodes)))
        return result

    def _load(self, session: Session, item: WorkItem, progress: Callable[[str], None] | None = None) -> Graph:
        workspace = GitWorkspace(Path(item.project.repository_path), self.worktrees, item.id, item.title)
        graph = Graph(item.entry_node_id, workspace, make_node=self._make_node, progress=progress)
        raw_data = {row.id: row.data or {} for row in item.nodes}
        edges = list(session.scalars(select(EdgeRecord).join(EdgeRecord.from_node)
                                     .where(NodeRecord.work_item_id == item.id).order_by(EdgeRecord.id)))
        historical_departures = {edge.from_node_id for edge in edges if edge.status == EdgeStatus.APPROVED}
        nodes = {}
        for row in item.nodes:
            cls = NODE_CLASSES.get(row.node_type.value)
            if cls is None:
                raise ValueError(f'Node {row.id} has unsupported type {row.node_type.value!r}.')
            data = _node_data(row, raw_data)
            legacy = raw_data[row.id].get('_workflow', {})
            status = row.status or legacy.get('status') or (
                NodeStatus.DONE if row.id in historical_departures else NodeStatus.PENDING
            )
            state = NodeState(
                data=NODE_DATA[row.node_type.value].validate_python(data),
                id=row.id, status=NodeStatus(status), model=row.model, conversation=row.conversation,
                branch_ref=row.branch_ref, commit_sha=row.commit_sha,
            )
            nodes[row.id] = self._make_node(cls, state, graph)
        graph.nodes.extend(nodes.values())
        graph.edges.extend(
            Edge(nodes[row.from_node_id], nodes[row.to_node_id], row.outbound_order, row.outcome,
                 (row.data or {}).get('note') or '', EdgeStatus(row.status), row.id)
            for row in edges
        )
        return graph

    def _make_node(self, cls: type[Node], state: NodeState, graph: Graph) -> Node:
        return cls(state, graph, self.agent)


def _node_data(row: NodeRecord, raw_data: dict[int, dict]) -> dict:
    # Older rows stored the brief and plan on predecessor records.
    data = dict(raw_data[row.id])
    if row.node_type == NodeType.TECHNICAL_PLANNING and 'brief' not in data:
        goal = raw_data.get(data.get('goal_id'), {})
        data['brief'] = goal.get('approved') or goal.get('summary') or goal.get('draft') or ''
    if row.node_type == NodeType.IMPLEMENTATION and 'plan' not in data:
        plan = raw_data.get(data.get('plan_id'), {})
        goal = raw_data.get(plan.get('goal_id'), {})
        data['plan'] = plan.get('approved') or plan.get('summary') or plan.get('draft') or ''
        data['brief'] = plan.get('brief') or goal.get('approved') or goal.get('summary') or goal.get('draft') or ''
    if 'summary' not in data:
        data['summary'] = data.get('draft') or data.get('approved')
    return data


def _node_states(graph: Graph) -> dict[int, NodeState]:
    return {node.id: node.state for node in graph.nodes}


def _edge_statuses(graph: Graph) -> dict[int, EdgeStatus]:
    return {edge.id: edge.status for edge in graph.edges}


def _item(session: Session, item_id: int) -> WorkItem:
    item = session.get(WorkItem, item_id)
    if item is None:
        raise LookupError(f'Work item {item_id} does not exist')
    return item
