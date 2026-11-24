import json
from collections.abc import Callable
from pathlib import Path

from harness.agents.harness import AgentHarness, AgentProfile
from harness.graph.state import Edge, Graph, Node
from harness.graph.traverser import Edit, NewNode, Outcome


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


class Implementation(Node):
    def init(self, graph: Graph, message: str, worktree: Path, agents: AgentHarness,
             save_commit: Callable[[Path], str], progress: Callable[[str], None] | None) -> Outcome:
        data = self.data or {}
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
            if edge.to_node_id == self.id and edge.outcome == 'feedback'
        ), None)
        if feedback:
            prompt += f"\n\nReview feedback\n{feedback}"
        if message and message != feedback:
            prompt += f"\n\nRequest\n{message}"
        return self._turn(prompt, worktree, agents, save_commit, progress)

    def follow_up(self, _graph: Graph, message: str, worktree: Path, agents: AgentHarness,
                  save_commit: Callable[[Path], str], progress: Callable[[str], None] | None) -> Outcome:
        return self._turn(message, worktree, agents, save_commit, progress)

    def _turn(self, prompt: str, worktree: Path, agents: AgentHarness, save_commit: Callable[[Path], str],
              progress: Callable[[str], None] | None) -> Outcome:
        model = agents.model
        data = self.data or {}
        result = agents.run_turn(
            prompt, profile=PROFILE, model=model, conversation=self.conversation, worktree=worktree,
            node_id=self.id, progress=progress,
        )
        self.commit_sha = save_commit(worktree)
        self.model = model
        self.conversation = result.conversation
        if result.paused:
            self.data = {**data, "paused": True}
            return Outcome("paused")
        self.data = {**data, "paused": False, "summary": result.output}
        _, _, last_line = result.output.rstrip().rpartition('\n')
        if last_line.startswith('PREREQUISITES:'):
            try:
                briefs = json.loads(last_line.removeprefix('PREREQUISITES:'))
            except json.JSONDecodeError:
                briefs = None
            if isinstance(briefs, list) and briefs and all(isinstance(brief, str) and brief.strip() for brief in briefs):
                return Outcome('blocked', {'briefs': briefs})
        return Outcome("review")

    def apply_turn(self, edit: Edit, outcome: Outcome, suspend: Callable[[Edit, Node, list[str]], Edge],
                   successor: Callable[[Edit, Node, NewNode, Outcome], Edge]) -> Edge | None:
        if outcome.name == 'blocked':
            return suspend(edit, self, outcome.data['briefs'])
        if outcome.name == 'review':
            return successor(edit, self, NewNode('human_review', {'target_id': self.id}), outcome)
        return None

    def continuation(self) -> NewNode:
        return NewNode(self.node_type, {**(self.data or {}), 'paused': True}, commit_sha=self.commit_sha,
                       conversation=self.conversation)
