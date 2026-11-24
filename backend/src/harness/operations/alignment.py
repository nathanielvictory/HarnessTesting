from collections.abc import Callable
from pathlib import Path

from harness.agents.harness import AgentHarness, AgentProfile, READ_ONLY_FILE_TOOLS
from harness.graph.state import Graph, Node
from harness.graph.traverser import NewNode, Outcome


PROFILE = AgentProfile(
    instructions=(
        "Help the user agree on the outcome of a work item. Inspect the repository's documentation "
        "and code when they can clarify the goal. Ask a focused question when necessary. "
        "When the intent is clear, answer with a concise proposed brief covering the outcome, "
        "constraints, and how the user will recognize success. Leave technical implementation to planning."
    ),
    file_tools=READ_ONLY_FILE_TOOLS,
)


class GoalAlignment(Node):
    def init(self, _graph: Graph, message: str, worktree: Path, agents: AgentHarness,
             _save_commit: Callable[[Path], str], progress: Callable[[str], None] | None) -> Outcome:
        data = self.data or {}
        message = message or 'Draft the brief.'
        if seed := data.get('scope_brief'):
            message = f'Scoped work: {seed}\n\n{message}'
        if data.get("previous_brief"):
            message = f"Previous brief\n{data['previous_brief']}\n\nRevision request\n{message}"
        return self._turn(message, worktree, agents, progress)

    def follow_up(self, _graph: Graph, message: str, worktree: Path, agents: AgentHarness,
                  _save_commit: Callable[[Path], str], progress: Callable[[str], None] | None) -> Outcome:
        return self._turn(message, worktree, agents, progress)

    def _turn(self, message: str, worktree: Path, agents: AgentHarness,
              progress: Callable[[str], None] | None) -> Outcome:
        model = agents.model
        result = agents.run_turn(
            message, profile=PROFILE, model=model, conversation=self.conversation, worktree=worktree,
            node_id=self.id, progress=progress,
        )
        self.model = model
        self.conversation = result.conversation
        if result.paused:
            return Outcome("paused")
        self.data = {**(self.data or {}), "draft": result.output}
        return Outcome("reply")

    def confirm_transition(self, base: Callable[[], str], *, delegating: bool) -> NewNode:
        data = self.data or {}
        draft = data.get('draft')
        if not draft:
            raise ValueError('There is no draft to approve yet.')
        if delegating:
            raise ValueError('Only an approved plan can delegate its implementation to scoped pieces.')
        self.data = {**data, 'approved': draft, 'base_commit': base()}
        return NewNode('technical_planning', {'goal_id': self.id})
