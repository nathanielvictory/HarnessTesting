from collections.abc import Callable

from harness.agents.harness import AgentHarness, AgentProfile, READ_ONLY_FILE_TOOLS
from harness.git.repository import GitRepository
from harness.graph.state import Node
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
    def __init__(self, repository: GitRepository, agents: AgentHarness, *,
                 progress: Callable[[str], None] | None = None) -> None:
        self.repository = repository
        self.agents = agents
        self.progress = progress

    def talk(self, node: Node, message: str) -> Outcome:
        data = node.data or {}
        if node.conversation is None and data.get("previous_brief"):
            message = f"Previous brief\n{data['previous_brief']}\n\nRevision request\n{message}"
        base = data.get("base_commit") or self.repository.commit_sha()
        model = self.agents.model
        with self.repository.inspection_checkout(base) as checkout:
            result = self.agents.run_turn(
                message, profile=PROFILE, model=model, conversation=node.conversation, worktree=checkout,
                node_id=node.id, progress=self.progress,
            )
        node.model = model
        node.conversation = result.conversation
        node.data = {**data, "base_commit": base}
        if result.paused:
            return Outcome("paused")
        node.data["draft"] = result.output
        return Outcome("reply")
