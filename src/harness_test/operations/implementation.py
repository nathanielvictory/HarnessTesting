from pathlib import Path

from harness_test.agents.harness import AgentHarness, AgentProfile
from harness_test.git.repository import GitRepository
from harness_test.graph.state import Node
from harness_test.graph.traverser import Outcome


PROFILE = AgentProfile(
    instructions=(
        "Implement the approved brief and technical plan in the assigned checkout. "
        "Address review feedback when provided. The harness saves the Git commit. "
        "Finish with a concise summary of changes and anything left to verify."
    ),
    file_tools=("read_file", "list_files", "grep", "edit_file", "write_file"),
)


class Implementation:
    def __init__(self, repository: GitRepository, agents: AgentHarness) -> None:
        self.repository = repository
        self.agents = agents

    def run(
        self,
        node: Node,
        *,
        brief: str,
        plan: str,
        feedback: str | None,
        checkout_path: Path,
        branch_ref: str,
        base_commit: str,
        commit_message: str,
    ) -> Outcome:
        branch = node.branch_ref or branch_ref
        commit = node.commit_sha or base_commit
        worktree = self.repository.open_worktree(checkout_path, branch, commit)
        model = node.model or self.agents.model
        data = node.data or {}
        prompt = f"Approved brief\n{brief}\n\nApproved technical plan\n{plan}"
        if data.get("paused"):
            prompt += "\n\nContinue the interrupted implementation from the saved checkout."
        elif feedback:
            prompt += f"\n\nReview feedback\n{feedback}"
        result = self.agents.run_turn(
            prompt, profile=PROFILE, model=model, conversation=node.conversation, worktree=worktree
        )
        node.commit_sha = self.repository.save_commit(worktree, commit_message)
        node.branch_ref = branch
        node.model = model
        node.conversation = result.conversation
        if result.paused:
            node.data = {**data, "paused": True}
            return Outcome("paused")
        node.data = {**data, "paused": False, "summary": result.output}
        return Outcome("review")
