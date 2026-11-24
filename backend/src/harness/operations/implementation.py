import json
from collections.abc import Callable
from pathlib import Path

from harness.agents.harness import AgentHarness, AgentProfile
from harness.git.repository import GitRepository
from harness.graph.state import Graph, Node
from harness.graph.traverser import Outcome


PROFILE = AgentProfile(
    instructions=(
        "Implement the approved brief and technical plan in the assigned checkout. "
        "Address review feedback when provided. The harness saves the Git commit. "
        "If work cannot continue without separately scoped prerequisites, stop with your edits saved "
        "and put PREREQUISITES: followed by a JSON array of short scoped briefs on the last line. "
        "Otherwise finish with a concise summary of changes and anything left to verify."
    ),
    file_tools=("read_file", "list_files", "grep", "edit_file", "write_file"),
)


class Implementation:
    def __init__(self, repository: GitRepository, agents: AgentHarness, commit_message: str, *,
                 progress: Callable[[str], None] | None = None) -> None:
        self.repository = repository
        self.agents = agents
        self.commit_message = commit_message
        self.progress = progress

    def start(self, graph: Graph, node: Node, message: str, worktree: Path) -> Outcome:
        data = node.data or {}
        plan = graph.node(data['plan_id'])
        plan_data = plan.data or {}
        goal = graph.node(plan_data['goal_id'])
        brief = (goal.data or {})['approved']
        prompt = f"Approved brief\n{brief}\n\nApproved technical plan\n{plan_data['approved']}"
        if data.get("revision_note"):
            prompt += f"\n\nRevision request\n{data['revision_note']}"
        if data.get("paused"):
            prompt += "\n\nContinue the interrupted implementation from the saved checkout."
        feedback = data.get('feedback') or next((
            (edge.data or {}).get('note') for edge in reversed(graph.history())
            if edge.to_node_id == node.id and edge.outcome == 'feedback'
        ), None)
        if feedback:
            prompt += f"\n\nReview feedback\n{feedback}"
        if message and message != feedback:
            prompt += f"\n\nRequest\n{message}"
        return self._turn(node, prompt, worktree)

    def follow_up(self, _graph: Graph, node: Node, message: str, worktree: Path) -> Outcome:
        return self._turn(node, message, worktree)

    def _turn(self, node: Node, prompt: str, worktree: Path) -> Outcome:
        model = self.agents.model
        data = node.data or {}
        result = self.agents.run_turn(
            prompt, profile=PROFILE, model=model, conversation=node.conversation, worktree=worktree,
            node_id=node.id, progress=self.progress,
        )
        node.commit_sha = self.repository.save_commit(worktree, self.commit_message)
        node.model = model
        node.conversation = result.conversation
        if result.paused:
            node.data = {**data, "paused": True}
            return Outcome("paused")
        node.data = {**data, "paused": False, "summary": result.output}
        _, _, last_line = result.output.rstrip().rpartition('\n')
        if last_line.startswith('PREREQUISITES:'):
            try:
                briefs = json.loads(last_line.removeprefix('PREREQUISITES:'))
            except json.JSONDecodeError:
                briefs = None
            if isinstance(briefs, list) and briefs and all(isinstance(brief, str) and brief.strip() for brief in briefs):
                return Outcome('blocked', {'briefs': briefs})
        return Outcome("review")
