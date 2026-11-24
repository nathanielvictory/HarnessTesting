from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from harness.agents.harness import AgentHarness
from harness.git.repository import GitRepository
from harness.graph.state import Edge, Graph, Node
from harness.graph.traverser import Edit, NewNode, Outcome, Step, Traverser
from harness.persistence.graph.repository import GraphRepository
from harness.persistence.models import NodeType

from .review import ReviewDecision, record_review


@dataclass(frozen=True)
class ScopedWork:
    brief: str
    # Zero-based indexes into this batch. An empty list means independent.
    depends_on: list[int] = field(default_factory=list)


class WorkSession:
    def __init__(self, item_id: int, store: GraphRepository, repository: GitRepository,
                 agents: AgentHarness, worktrees: Path, title: str | None, *,
                 progress: Callable[[str], None] | None = None) -> None:
        self.item_id = item_id
        self.store = store
        self.repository = repository
        self.worktrees = worktrees
        self.agents = agents
        self.progress = progress
        self.save_commit = partial(repository.save_commit, message=title or f'Work item {item_id}')

    def graph(self) -> Graph:
        return self.store.load(self.item_id)

    def start(self, node_id: int, message: str = '') -> Step:
        return self._run_agent(node_id, message.strip(), starting=True)

    def follow_up(self, node_id: int, message: str) -> Step:
        if not message.strip():
            raise ValueError('Enter a message.')
        return self._run_agent(node_id, message.strip(), starting=False)

    def approve(self, node_id: int, pieces: list[ScopedWork] | None = None) -> Step:
        graph, node = self._current(node_id)
        destination: NewNode | None = None

        def confirm(current: Node) -> Outcome:
            nonlocal destination
            transition = getattr(current, 'confirm_transition', None)
            if transition is None:
                raise ValueError('There is no draft to approve yet.')
            destination = transition(lambda: self._base(graph, current), delegating=pieces is not None)
            return Outcome('approved')

        def apply(edit: Edit, source: Node, outcome: Outcome) -> Edge | None:
            source.update_workflow(status='done')
            if pieces is None:
                assert destination is not None
                return self._successor(edit, source, destination, outcome)
            children = self._spawn(edit, source, pieces, split=True)
            source.update_workflow(split=[child.id for child in children])
            return None

        return self._advance(node, confirm, apply)

    def _run_agent(self, node_id: int, message: str, *, starting: bool) -> Step:
        graph, node = self._current(node_id)
        turn_name = 'init' if starting else 'follow_up'
        if not hasattr(node, turn_name):
            raise ValueError(f'Node {node.id} has no subagent.')
        if starting and node.conversation is not None:
            raise ValueError('This node already has a conversation. Send a follow-up instead.')
        if not starting and node.conversation is None:
            raise ValueError('Start this node before sending a follow-up.')

        def run(current: Node) -> Outcome:
            base = self._base(graph, current, snapshot=current.commit_sha)
            if current.commit_sha is None:
                current.data = {**_data(current), 'base_commit': base}
            checkout = self._open_checkout(current, base, legacy_path=self.worktrees / str(current.id))
            return getattr(current, turn_name)(graph, message, checkout, self.agents, self.save_commit, self.progress)

        def apply(edit: Edit, source: Node, outcome: Outcome) -> Edge | None:
            apply_turn = getattr(source, 'apply_turn', None)
            if apply_turn is None:
                return None
            return apply_turn(edit, outcome, suspend, self._successor)

        def suspend(edit: Edit, source: Node, briefs: list[str]) -> Edge:
            return self._suspend(edit, source, [ScopedWork(brief) for brief in briefs])

        return self._advance(node, run, apply)

    def discover(self, pieces: list[ScopedWork], node_id: int) -> Step:
        _, node = self._current(node_id)
        return self._advance(node, lambda _: Outcome('blocked'),
                             lambda edit, source, _: self._suspend(edit, source, pieces))

    def _spawn(self, edit: Edit, source: Node, pieces: list[ScopedWork], *, split: bool) -> list[Node]:
        if not pieces or any(not piece.brief.strip() for piece in pieces):
            raise ValueError('Enter a brief for each scoped piece.')
        if any(not 0 <= index < len(pieces) for piece in pieces for index in piece.depends_on):
            raise ValueError('Scoped prerequisites must refer to pieces in the same batch.')
        children = [edit.add(NewNode(NodeType.GOAL_ALIGNMENT, {'scope_brief': piece.brief.strip()}))
                    for piece in pieces]
        inherited = self._required_scopes(edit.graph, source)
        for child, piece in zip(children, pieces, strict=True):
            child.update_workflow(scope=child.id, requires=sorted(inherited | {children[i].id for i in piece.depends_on}),
                                  after=[source.id] if split else [])
            edit.transition(source, child, 'delegated' if split else 'discovered')
        return children

    def _suspend(self, edit: Edit, source: Node, pieces: list[ScopedWork]) -> Edge:
        children = self._spawn(edit, source, pieces, split=False)
        source.update_workflow(status='done')
        continuation = getattr(source, 'continuation', None)
        resume = edit.add(continuation() if continuation else NewNode(
            source.node_type, {**_data(source)}, commit_sha=source.commit_sha, conversation=source.conversation,
        ))
        resume.update_workflow(scope=edit.graph.scope(source), after=[source.id],
                               requires=[child.id for child in children])
        return edit.transition(source, resume, 'interrupted', {'prerequisites': [child.id for child in children]})

    def earlier_steps(self, node_id: int) -> list[Node]:
        graph, review = self._current(node_id, NodeType.HUMAN_REVIEW)
        target = graph.node(_data(review)['target_id'])
        if target.node_type != NodeType.IMPLEMENTATION:
            return []
        plan = graph.node(_data(target)['plan_id'])
        return [plan, graph.node(_data(plan)['goal_id'])]

    def review(self, decision: ReviewDecision, note: str = '', *, node_id: int,
               earlier_id: int | None = None) -> Step:
        graph, review = self._current(node_id, NodeType.HUMAN_REVIEW)
        data = _data(review)
        target = graph.node(data['target_id'])
        is_implementation = target.node_type == NodeType.IMPLEMENTATION
        earlier = self.earlier_steps(review.id) if decision is ReviewDecision.REVIEW_EARLIER else []
        if decision in (ReviewDecision.FEEDBACK, ReviewDecision.REVISE) and not note.strip():
            raise ValueError('Describe what should change.')

        def apply(edit: Edit, source: Node, outcome: Outcome) -> Edge | None:
            match decision:
                case ReviewDecision.ACCEPT if is_implementation and target.commit_sha:
                    source.update_workflow(status='done', accepted_commit=target.commit_sha)
                    return None
                case ReviewDecision.FEEDBACK if is_implementation:
                    destination = NewNode(NodeType.IMPLEMENTATION, {**_data(target), 'feedback': note},
                                          commit_sha=target.commit_sha, conversation=target.conversation)
                case ReviewDecision.REVISE:
                    return self._reopen(edit, edit.graph.node(target.id), note, source)
                case ReviewDecision.REVIEW_EARLIER if is_implementation:
                    if earlier_id not in {item.id for item in earlier}:
                        raise ValueError("Choose an earlier step in this implementation's plan.")
                    destination = NewNode(NodeType.HUMAN_REVIEW, {
                        'target_id': earlier_id, 'return_review_id': review.id,
                    })
                case ReviewDecision.RETURN if 'return_review_id' in data:
                    original = edit.graph.node(data['return_review_id'])
                    destination = NewNode(NodeType.HUMAN_REVIEW, {'target_id': _data(original)['target_id']})
                case _:
                    raise ValueError(f'{decision.value} is unavailable for this review.')
            return self._successor(edit, source, destination, outcome)

        return self._advance(review, lambda current: record_review(current, target, decision, note), apply)

    def reopen(self, node_id: int, note: str) -> None:
        self.store.edit(self.item_id, lambda edit: self._reopen(edit, edit.graph.node(node_id), note))

    def _reopen(self, edit: Edit, target: Node, note: str, source: Node | None = None) -> Edge:
        if target.status == 'superseded' or target.node_type == NodeType.HUMAN_REVIEW or not note.strip():
            raise ValueError('Choose a live brief, plan, or implementation and describe what should change.')
        graph = edit.graph
        affected = {target.id}
        changed_scopes = {graph.scope(target)}
        retired: set[int] = set()
        while True:
            before = (len(affected), len(changed_scopes), len(retired))
            for node in graph.nodes.values():
                if node.status == 'superseded':
                    continue
                workflow = node.workflow
                scope = graph.scope(node)
                if retired.intersection(workflow.get('requires', [])) and scope != graph.scope(target):
                    # A discovered scope based on a withdrawn delegated piece is also withdrawn.
                    retired.add(scope)
                if scope in retired or affected.intersection(workflow.get('after', [])):
                    affected.add(node.id)
                elif changed_scopes.intersection(workflow.get('requires', [])):
                    # A never-started piece can keep waiting on the same stable scope.
                    if (node.node_type != NodeType.GOAL_ALIGNMENT or node.status != 'pending'
                            or node.conversation is not None or _data(node).get('draft')):
                        affected.add(node.id)
                if node.id in affected:
                    changed_scopes.add(scope)
                    retired.update(workflow.get('split', []))
                if changed_scopes.intersection(workflow.get('split', [])):
                    changed_scopes.add(scope)
            if before == (len(affected), len(changed_scopes), len(retired)):
                break

        edge = None
        for key in sorted(affected):
            node = graph.node(key)
            workflow = node.workflow
            node.update_workflow(status='superseded')
            if graph.scope(node) in retired or affected.intersection(workflow.get('after', [])):
                continue
            data = _data(node)
            fresh = {name: data[name] for name in ('scope_brief', 'goal_id', 'plan_id') if name in data}
            fresh['revision_note'] = note.strip() if key == target.id else 'A prerequisite was revised.'
            if node.node_type == NodeType.GOAL_ALIGNMENT and data.get('approved'):
                fresh['previous_brief'] = data['approved']
            if node.node_type == NodeType.TECHNICAL_PLANNING and data.get('approved'):
                fresh['previous_plan'] = data['approved']
            required = set(workflow.get('requires', []))
            attempts = {node.id}
            for transition in graph.history():
                if transition.outcome == 'interrupted' and transition.from_node_id in attempts:
                    attempts.add(transition.to_node_id)
                    required.update((transition.data or {}).get('prerequisites', []))
            replacement = edit.add(NewNode(node.node_type, fresh))
            replacement.update_workflow(scope=graph.scope(node), after=workflow.get('after', []),
                                        requires=sorted(required - retired))
            transition = edit.transition(source if source is not None and key == target.id else node,
                                         replacement, 'reopened',
                                         {'replaces': key, 'note': fresh['revision_note']})
            if key == target.id:
                edge = transition
        if edge is None:
            raise ValueError('Reopen the prerequisite before revising work that depends on it.')
        return edge

    def _current(self, node_id: int, node_type: NodeType | None = None) -> tuple[Graph, Node]:
        graph = self.graph()
        node = graph.select(node_id)
        if node_type is not None and node.node_type != node_type:
            raise ValueError(f'Node {node.id} is {node.node_type}, expected {node_type.value}.')
        return graph, node

    def _advance(self, node: Node, operation: Callable[[Node], Outcome],
                 apply: Callable[[Edit, Node, Outcome], Edge | None] | None = None) -> Step:
        runner = Traverser(self.store, {node.node_type: operation}, apply or (lambda *_: None), self._finalize)
        return runner.advance(self.item_id, node.id)

    @staticmethod
    def _successor(edit: Edit, source: Node, destination: NewNode, outcome: Outcome) -> Edge:
        source.update_workflow(status='done')
        target = edit.add(destination)
        target.update_workflow(scope=edit.graph.scope(source), after=[source.id])
        return edit.transition(source, target, outcome.name, outcome.data)

    @staticmethod
    def _required_scopes(graph: Graph, node: Node) -> set[int]:
        required: set[int] = set()
        seen: set[int] = set()
        frontier = [node.id]
        while frontier:
            key = frontier.pop()
            if key in seen:
                continue
            seen.add(key)
            workflow = graph.node(key).workflow
            required.update(workflow.get('requires', []))
            frontier.extend(workflow.get('after', []))
        return required

    def _base(self, graph: Graph, node: Node, *, snapshot: str | None = None) -> str:
        required = self._required_scopes(graph, node)
        scopes = graph.scopes()
        frontier = list(required)
        while frontier:
            for member in scopes[frontier.pop()]:
                for child in member.workflow.get('split', []):
                    if child not in required:
                        required.add(child)
                        frontier.append(child)
        revisions = [commit for key in sorted(required) for member in scopes[key]
                     if (commit := member.workflow.get('accepted_commit'))]
        return self.repository.integrate(self.item_id, snapshot or self._root_base(graph), revisions)

    def _root_base(self, graph: Graph) -> str:
        entry = graph.node(graph.entry_node_id)
        return _data(entry).get('base_commit') or self.repository.commit_sha()

    def _finalize(self, graph: Graph) -> str:
        revisions = [commit for node in sorted(graph.nodes.values(), key=lambda node: node.id)
                     if node.status == 'done' and (commit := node.workflow.get('accepted_commit'))]
        return self.repository.integrate(self.item_id, self._root_base(graph), revisions, final=True)

    def _open_checkout(self, node: Node, commit: str, *, legacy_path: Path | None = None) -> Path:
        checkout = self.worktrees / 'items' / str(self.item_id)
        checkout.parent.mkdir(parents=True, exist_ok=True)
        node.branch_ref = node.branch_ref or f'refs/heads/harness/{self.item_id}-{node.id}'
        return self.repository.open_worktree(checkout, node.branch_ref, commit, legacy_path=legacy_path)


def _data(node: Node) -> dict:
    return node.data or {}
