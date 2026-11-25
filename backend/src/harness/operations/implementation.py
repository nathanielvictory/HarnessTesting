from dataclasses import dataclass
from typing import Annotated

from pydantic import StringConstraints
from pydantic_ai import Tool

from harness.agents.harness import AgentTurn
from harness.graph.node import Node, NodeData, NodeState

from .review import Review, ReviewData


@dataclass(kw_only=True)
class ImplementationData(NodeData):
    brief: str
    plan: str
    paused: bool = False
    feedback: str | None = None
    revision_note: str | None = None


class Implementation(Node[ImplementationData]):
    node_type = 'implementation'
    data_type = ImplementationData
    saves_changes = True
    _review_summary: str | None = None

    def initial_prompt(self, message: str) -> tuple[str, str]:
        instructions = (
            "Implement the brief and technical plan in the assigned checkout. "
            "Address review feedback when provided. The harness saves the Git commit. "
            "Finish with a concise summary of changes and anything left to verify. Report anything that blocks the work. "
            "When the work is ready for review, call create_review_node with the summary. "
            "Call it again if the user wants to send an updated result for review."
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

    def model_tools(self) -> tuple[str | Tool[None], ...]:
        return (
            'read_file', 'list_files', 'grep', 'edit_file', 'write_file',
            Tool(self.create_review_node, sequential=True),
        )

    def create_review_node(
        self, summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)],
    ) -> str:
        """Create a review node for the saved changes and summary at the end of this turn."""
        self._review_summary = summary
        return 'A review node will be created for the saved result of this turn.'

    def _run(self, prompt: str, *, instructions: str | None = None) -> AgentTurn:
        self._review_summary = None
        reply = super()._run(prompt, instructions=instructions)
        if self._review_summary is not None and not reply.paused:
            data = ReviewData(
                reviewed_commit_sha=self.state.commit_sha, summary=self._review_summary,
            )
            self.graph.create_nodes(self, Review, [NodeState(data)], 'review')
        return reply
