from collections.abc import Callable
from pathlib import Path

from harness.agents.harness import AgentHarness, AgentProfile, READ_ONLY_FILE_TOOLS
from harness.graph.state import Graph, Node
from harness.graph.traverser import NewNode, Outcome


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


class TechnicalPlanning(Node):
    def init(self, graph: Graph, message: str, worktree: Path, agents: AgentHarness,
             _save_commit: Callable[[Path], str], progress: Callable[[str], None] | None) -> Outcome:
        data = self.data or {}
        goal = graph.node(data['goal_id'])
        brief = (goal.data or {})['approved']
        message = message or 'Draft the technical plan.'
        if data.get("previous_plan"):
            message = f"Previous plan\n{data['previous_plan']}\n\nRevision request\n{message}"
        return self._turn(f"Approved brief\n{brief}\n\nRequest\n{message}", worktree, agents, progress)

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

    def confirm_transition(self, base: Callable[[], str], *, delegating: bool) -> NewNode | None:
        data = self.data or {}
        draft = data.get('draft')
        if not draft:
            raise ValueError('There is no draft to approve yet.')
        self.data = {**data, 'approved': draft, 'base_commit': base()}
        return None if delegating else NewNode('implementation', {'plan_id': self.id})
