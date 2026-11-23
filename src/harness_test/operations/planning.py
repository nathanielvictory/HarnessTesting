from harness_test.agents.harness import AgentHarness, AgentProfile
from harness_test.git.repository import GitRepository
from harness_test.graph.state import Node
from harness_test.graph.traverser import Outcome


PROFILE = AgentProfile(
    instructions=(
        "Propose a concise technical plan for the approved brief. Inspect the repository as needed. "
        "Identify the affected components, implementation steps, and verification. "
        "If the user asks for changes, reply with the complete revised plan."
    ),
    file_tools=("read_file", "list_files", "grep"),
)


class TechnicalPlanning:
    def __init__(self, repository: GitRepository, agents: AgentHarness) -> None:
        self.repository = repository
        self.agents = agents

    def talk(self, node: Node, brief: str, message: str) -> Outcome:
        data = node.data or {}
        if node.conversation is None and data.get("previous_plan"):
            message = f"Previous plan\n{data['previous_plan']}\n\nRevision request\n{message}"
        prompt = f"Approved brief\n{brief}\n\nRequest\n{message}"
        model = node.model or self.agents.model
        with self.repository.inspection_checkout(data["base_commit"]) as checkout:
            result = self.agents.run_turn(
                prompt, profile=PROFILE, model=model, conversation=node.conversation, worktree=checkout
            )
        node.model = model
        node.conversation = result.conversation
        if result.paused:
            return Outcome("paused")
        node.data = {**data, "draft": result.output}
        return Outcome("reply")
