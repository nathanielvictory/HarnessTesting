from collections.abc import Callable
from pathlib import Path

from harness.agents.harness import AgentHarness
from harness.git.repository import GitRepository
from harness.graph.state import Graph, Node
from harness.graph.traverser import NewNode, Outcome, Step, Traverser
from harness.persistence.graph.repository import GraphRepository
from harness.persistence.models import NodeType

from .alignment import GoalAlignment
from .implementation import Implementation
from .planning import TechnicalPlanning
from .review import ReviewDecision, record_review


class WorkSession:
    """Application operations for one selected work item."""

    def __init__(self, item_id: int, store: GraphRepository, repository: GitRepository,
                 agents: AgentHarness, worktrees: Path, title: str | None, *,
                 progress: Callable[[str], None] | None = None) -> None:
        self.item_id = item_id
        self.store = store
        self.repository = repository
        self.worktrees = worktrees
        self.title = title or f"Work item {item_id}"
        self.alignment = GoalAlignment(agents, progress=progress)
        self.planning = TechnicalPlanning(agents, progress=progress)
        self.implementation = Implementation(repository, agents, progress=progress)

    def graph(self) -> Graph:
        return self.store.load(self.item_id)

    def talk(self, message: str) -> Step:
        graph, node = self._current()
        match node.node_type:
            case NodeType.GOAL_ALIGNMENT:
                base = _data(node).get("base_commit") or self.repository.commit_sha()

                def align(current: Node) -> Outcome:
                    current.data = {**_data(current), "base_commit": base}
                    return self.alignment.talk(current, message, self._open_checkout(current, base))

                return self._advance(node, align)
            case NodeType.TECHNICAL_PLANNING:
                goal = graph.node(_data(node)["goal_id"])
                base = _data(node)["base_commit"]

                def plan(current: Node) -> Outcome:
                    return self.planning.talk(current, _data(goal)["approved"], message, self._open_checkout(current, base))

                return self._advance(node, plan)
            case _:
                raise ValueError("The current node is waiting for an implementation or review action.")

    def approve(self) -> Step:
        _, node = self._current()
        data = _data(node)
        draft = data.get("draft")
        if not draft:
            raise ValueError("There is no draft to approve yet.")
        branch = self._branch_ref(node)
        match node.node_type:
            case NodeType.GOAL_ALIGNMENT:
                base = self.repository.commit_sha(data.get("base_commit") or "HEAD")
                data = {**data, "base_commit": base}
                destination = NewNode(NodeType.TECHNICAL_PLANNING, {"goal_id": node.id, "base_commit": base}, branch)
            case NodeType.TECHNICAL_PLANNING:
                destination = NewNode(NodeType.IMPLEMENTATION, {"plan_id": node.id}, branch)
            case _:
                raise ValueError("Only goal alignment and planning have drafts to approve.")

        def approve_draft(current: Node) -> Outcome:
            current.data = {**data, "approved": draft}
            current.branch_ref = branch
            return Outcome("approved")

        return self._advance(node, approve_draft, destination)

    def implement(self) -> Step:
        graph, node = self._current(NodeType.IMPLEMENTATION)
        plan = graph.node(_data(node)["plan_id"])
        goal = graph.node(_data(plan)["goal_id"])
        history = graph.history()
        feedback = None
        if history and history[-1].outcome == ReviewDecision.FEEDBACK:
            feedback = (history[-1].data or {}).get("note")
        def run(current: Node) -> Outcome:
            current.branch_ref = current.branch_ref or plan.branch_ref or self._branch_ref(current)
            checkout = self._open_checkout(
                current, current.commit_sha or _data(plan)["base_commit"],
                legacy_path=self.worktrees / str(current.id),
            )
            return self.implementation.run(
                current, brief=_data(goal)["approved"], plan=_data(plan)["approved"], feedback=feedback,
                worktree=checkout, commit_message=self.title,
            )

        return self._advance(node, run, NewNode(NodeType.HUMAN_REVIEW, {"target_id": node.id}))

    def _branch_ref(self, node: Node) -> str:
        return node.branch_ref or f"refs/heads/harness/{self.item_id}-{node.id}"

    def _open_checkout(self, node: Node, commit: str, *, legacy_path: Path | None = None) -> Path:
        checkout = self.worktrees / "items" / str(self.item_id)
        checkout.parent.mkdir(parents=True, exist_ok=True)
        node.branch_ref = self._branch_ref(node)
        return self.repository.open_worktree(checkout, node.branch_ref, commit, legacy_path=legacy_path)

    def review_target(self) -> Node:
        graph, review = self._current(NodeType.HUMAN_REVIEW)
        return graph.node(_data(review)["target_id"])

    def earlier_steps(self) -> list[Node]:
        graph, review = self._current(NodeType.HUMAN_REVIEW)
        target = graph.node(_data(review)["target_id"])
        if target.node_type != NodeType.IMPLEMENTATION:
            return []
        plan = graph.node(_data(target)["plan_id"])
        goal = graph.node(_data(plan)["goal_id"])
        return [plan, goal]

    def review(self, decision: ReviewDecision, note: str = "", *, earlier_id: int | None = None) -> Step:
        graph, review = self._current(NodeType.HUMAN_REVIEW)
        data = _data(review)
        target = graph.node(data["target_id"])
        is_implementation = target.node_type == NodeType.IMPLEMENTATION
        match decision:
            case ReviewDecision.ACCEPT if is_implementation:
                destination = None
            case ReviewDecision.FEEDBACK if is_implementation:
                destination = target.id
            case ReviewDecision.REVISE:
                destination = self._revision(graph, target, note, data.get("base_commit"))
            case ReviewDecision.REVIEW_EARLIER if is_implementation:
                if earlier_id not in {node.id for node in self.earlier_steps()}:
                    raise ValueError("Choose an earlier step in this implementation's plan.")
                plan = graph.node(_data(target)["plan_id"])
                destination = NewNode(NodeType.HUMAN_REVIEW, {
                    "target_id": earlier_id, "return_review_id": review.id,
                    "base_commit": _data(plan)["base_commit"],
                })
            case ReviewDecision.RETURN if "return_review_id" in data:
                destination = data["return_review_id"]
            case _:
                raise ValueError(f"{decision.value} is unavailable for this review.")
        return self._advance(review, lambda current: record_review(current, target, decision, note), destination)

    def _revision(self, graph: Graph, target: Node, note: str, base_commit: str | None) -> NewNode:
        if target.node_type == NodeType.IMPLEMENTATION:
            target = graph.node(_data(target)["plan_id"])
        data = _data(target)
        if target.node_type == NodeType.TECHNICAL_PLANNING:
            return NewNode(NodeType.TECHNICAL_PLANNING, {
                "goal_id": data["goal_id"], "base_commit": data["base_commit"],
                "previous_plan": data["approved"], "revision_note": note,
            })
        return NewNode(NodeType.GOAL_ALIGNMENT, {
            "previous_brief": data["approved"], "revision_note": note, "base_commit": base_commit,
        })

    def _current(self, node_type: NodeType | None = None) -> tuple[Graph, Node]:
        graph = self.graph()
        node = graph.current_node()
        if node is None:
            raise ValueError("This work item has no entry node.")
        if node_type is not None and node.node_type != node_type:
            raise ValueError(f"The work item is at {node.node_type}, expected {node_type.value}.")
        return graph, node

    def _advance(
        self, node: Node, operation: Callable[[Node], Outcome], destination: int | NewNode | None = None
    ) -> Step:
        runner = Traverser(
            self.store, {node.node_type: operation},
            lambda _graph, _node, outcome: None if outcome.name == "paused" else destination,
        )
        step = runner.advance(self.item_id)
        if step is None:
            raise ValueError("This work item has no entry node.")
        return step


def _data(node: Node) -> dict:
    return node.data or {}
