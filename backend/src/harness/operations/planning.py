from collections.abc import Callable

from harness.agents.harness import AgentHarness, AgentProfile, READ_ONLY_FILE_TOOLS
from harness.git.repository import GitRepository
from harness.graph.state import Node
from harness.graph.traverser import Outcome


PROFILE = AgentProfile(
    instructions=(
        "Propose a concise technical plan for the approved brief. Inspect the repository as needed. "
        "Identify the affected components, implementation steps, and verification. "
        "If the user asks for changes, reply with the complete revised plan."
    ),
    file_tools=READ_ONLY_FILE_TOOLS,
)


class TechnicalPlanning:
    def __init__(self, repository: GitRepository, agents: AgentHarness, *,
                 progress: Callable[[str], None] | None = None) -> None:
        self.repository = repository
        self.agents = agents
        self.progress = progress

    def talk(self, node: Node, brief: str, message: str) -> Outcome:
        data = node.data or {}
        if node.conversation is None and data.get("previous_plan"):
            message = f"Previous plan\n{data['previous_plan']}\n\nRevision request\n{message}"
        prompt = f"Approved brief\n{brief}\n\nRequest\n{message}"
        model = self.agents.model
        with self.repository.inspection_checkout(data["base_commit"]) as checkout:
            result = self.agents.run_turn(
                prompt, profile=PROFILE, model=model, conversation=node.conversation, worktree=checkout,
                progress=self.progress,
            )
        node.model = model
        node.conversation = result.conversation
        if result.paused:
            return Outcome("paused")
        node.data = {**data, "draft": result.output}
        return Outcome("reply")
