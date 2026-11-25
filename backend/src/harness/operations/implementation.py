from dataclasses import dataclass
from typing import Annotated

from pydantic import StringConstraints
from pydantic_ai import ToolOutput

from harness.agents.harness import AgentTurn
from harness.graph.node import Node, NodeData, NodeState

from .review import Review, ReviewData


@dataclass(frozen=True)
class ReviewRequest:
    """The completed implementation is ready for review."""

    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@dataclass(kw_only=True)
class ImplementationData(NodeData):
    brief: str
    plan: str
    checkpoint_sha: str | None = None
    paused: bool = False
    feedback: str | None = None
    revision_note: str | None = None


class Implementation(Node[ImplementationData]):
    node_type = 'implementation'
    data_type = ImplementationData

    def initial_prompt(self, message: str) -> tuple[str, str]:
        instructions = (
            "Implement the brief and technical plan in the assigned checkout. "
            "Address review feedback when provided. The harness saves the Git commit. "
            "When implementation is finished and ready for review, return create_review_node with a concise "
            "summary of the changes and anything left to verify. For questions, discussion, or blockers, reply with text."
        )
        data = self.state.data
        prompt = f"Brief\n{data.brief}\n\nTechnical plan\n{data.plan}"
        if data.revision_note:
            prompt += f"\n\nRevision request\n{data.revision_note}"
        if data.paused:
            prompt += "\n\nContinue the interrupted implementation from the saved checkout."
        if data.feedback:
            prompt += f"\n\nReview feedback\n{data.feedback}"
        if message and message != data.feedback:
            prompt += f"\n\nRequest\n{message}"
        return instructions, prompt

    def model_tools(self) -> tuple[str, ...]:
        return 'read_file', 'list_files', 'grep', 'edit_file', 'write_file'

    def _run(self, prompt: str, *, instructions: str | None = None) -> AgentTurn:
        agent = self.agent
        state = self.state
        workspace = self.graph.workspace
        commit_sha = state.data.checkpoint_sha or state.commit_sha
        checkout, state.branch_ref = workspace.prepare(self.id, state.branch_ref, commit_sha)
        reply = agent.run_turn(
            prompt, instructions=instructions, model=agent.model, conversation=state.conversation,
            worktree=checkout, node_id=self.id, progress=self.graph.progress,
            tools=self.model_tools(),
            output_type=[str, ToolOutput(ReviewRequest, name='create_review_node')],
        )
        commit_sha = workspace.save()
        state.data.checkpoint_sha = commit_sha
        state.model = agent.model
        state.conversation = reply.conversation
        if isinstance(reply.output, ReviewRequest):
            review = NodeState(ReviewData(summary=reply.output.summary), commit_sha=commit_sha)
            self.graph.create_nodes(self, Review, [review], 'review')
        return reply
