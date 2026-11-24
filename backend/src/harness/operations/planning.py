from collections.abc import Callable
from pathlib import Path

from harness.agents.harness import AgentHarness, AgentProfile, READ_ONLY_FILE_TOOLS
from harness.graph.state import Graph, Node
from harness.graph.traverser import Outcome


PROFILE = AgentProfile(
    instructions=(
        "Propose a concise technical plan for the approved brief. Inspect the repository as needed. "
        "Identify the affected components, implementation steps, and verification. "
        "If the work would benefit from separately reviewed pieces, list their briefs and "
        "name any prerequisites explicitly so the developer can delegate them when approving. "
        "If the user asks for changes, reply with the complete revised plan."
    ),
    file_tools=READ_ONLY_FILE_TOOLS,
)


class TechnicalPlanning:
    def __init__(self, agents: AgentHarness, *, progress: Callable[[str], None] | None = None) -> None:
        self.agents = agents
        self.progress = progress

    def start(self, graph: Graph, node: Node, message: str, worktree: Path) -> Outcome:
        data = node.data or {}
        goal = graph.node(data['goal_id'])
        brief = (goal.data or {})['approved']
        message = message or 'Draft the technical plan.'
        if data.get("previous_plan"):
            message = f"Previous plan\n{data['previous_plan']}\n\nRevision request\n{message}"
        return self._turn(node, f"Approved brief\n{brief}\n\nRequest\n{message}", worktree)

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
