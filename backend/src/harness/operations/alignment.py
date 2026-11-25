from dataclasses import dataclass
from typing import Annotated

from pydantic import StringConstraints
from pydantic_ai import Tool

from harness.graph.node import Node, NodeData, NodeState

from .planning import TechnicalPlanning, TechnicalPlanningData


@dataclass(kw_only=True)
class GoalAlignmentData(NodeData):
    goal: str | None = None


class GoalAlignment(Node[GoalAlignmentData]):
    node_type = 'goal_alignment'
    data_type = GoalAlignmentData

    def initial_prompt(self, message: str) -> tuple[str, str]:
        instructions = (
            "Help the user agree on the outcome of a work item. Inspect the repository's documentation "
            "and code when they can clarify the goal. Ask a focused question when necessary. "
            "When the intent is clear, answer with a concise proposed brief covering the outcome, "
            "constraints, and how the user will recognize success. Leave technical implementation to planning. "
            "When the user wants to send a brief to technical planning, call create_technical_planning_node "
            "with the complete brief. Call it again with the complete brief if the user wants to revise it."
        )
        if goal := self.state.data.goal:
            message = f"Goal\n{goal}\n\nRequest\n{message}" if message else goal
        return instructions, message or 'Draft the brief.'

    def model_tools(self) -> tuple[str | Tool[None], ...]:
        return ('read_file', 'list_files', 'grep', Tool(self.create_technical_planning_node, sequential=True))

    def create_technical_planning_node(
        self, brief: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)],
    ) -> str:
        """Create a technical planning node with the complete brief."""
        state = NodeState(TechnicalPlanningData(brief=brief), commit_sha=self.state.commit_sha)
        self.graph.create_nodes(self, TechnicalPlanning, [state], 'handoff')
        return 'Created a technical planning node.'
