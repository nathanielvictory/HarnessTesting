from collections.abc import Callable
from pathlib import Path

from harness.agents.harness import AgentHarness, AgentProfile, READ_ONLY_FILE_TOOLS
from harness.graph.state import Graph, Node
from harness.graph.traverser import Outcome


PROFILE = AgentProfile(
    instructions=(
        "Help the user agree on the outcome of a work item. Inspect the repository's documentation "
        "and code when they can clarify the goal. Ask a focused question when necessary. "
        "When the intent is clear, answer with a concise proposed brief covering the outcome, "
        "constraints, and how the user will recognize success. Leave technical implementation to planning."
    ),
    file_tools=READ_ONLY_FILE_TOOLS,
)


class GoalAlignment:
    def __init__(self, agents: AgentHarness, *, progress: Callable[[str], None] | None = None) -> None:
        self.agents = agents
        self.progress = progress

    def start(self, _graph: Graph, node: Node, message: str, worktree: Path) -> Outcome:
        data = node.data or {}
        message = message or 'Draft the brief.'
        if seed := data.get('scope_brief'):
            message = f'Scoped work: {seed}\n\n{message}'
        if data.get("previous_brief"):
            message = f"Previous brief\n{data['previous_brief']}\n\nRevision request\n{message}"
        return self._turn(node, message, worktree)

    def follow_up(self, _graph: Graph, node: Node, message: str, worktree: Path) -> Outcome:
        return self._turn(node, message, worktree)

    def _turn(self, node: Node, message: str, worktree: Path) -> Outcome:
        model = self.agents.model
        result = self.agents.run_turn(
            message, profile=PROFILE, model=model, conversation=node.conversation, worktree=worktree,
            node_id=node.id, progress=self.progress,
        )
        node.model = model
        node.conversation = result.conversation
        if result.paused:
            return Outcome("paused")
        node.data = {**(node.data or {}), "draft": result.output}
        return Outcome("reply")
