from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, StringConstraints
from pydantic_ai import Tool

from harness.graph.node import Node, NodeData, NodeState

from .implementation import Implementation, ImplementationData


@dataclass(kw_only=True)
class TechnicalPlanningData(NodeData):
    brief: str


class TechnicalPlanning(Node[TechnicalPlanningData]):
    node_type = 'technical_planning'
    data_type = TechnicalPlanningData

    def initial_prompt(self, message: str) -> tuple[str, str]:
        instructions = (
            "Write a concise technical plan for the brief. Inspect the repository as needed. "
            "Identify the affected components, implementation steps, and verification. "
            "If the user asks for changes, reply with the complete revised plan. "
            "When the user wants to proceed, call create_implementation_node with the complete plan. "
            "If the user wants to split the work, call create_alignment_nodes with the complete list of goals."
        )
        data = self.state.data
        message = message or 'Draft the technical plan.'
        return instructions, f"Brief\n{data.brief}\n\nRequest\n{message}"

    def model_tools(self) -> tuple[str | Tool[None], ...]:
        return (
            'read_file', 'list_files', 'grep',
            Tool(self.create_implementation_node, sequential=True),
            Tool(self.create_alignment_nodes, sequential=True),
        )

    def create_implementation_node(
        self, plan: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)],
    ) -> str:
        """Create an implementation node with the complete plan."""
        state = NodeState(ImplementationData(
            brief=self.state.data.brief, plan=plan,
        ), commit_sha=self.state.commit_sha)
        self.graph.create_nodes(self, Implementation, [state], 'handoff')
        return 'Created an implementation node.'

    def create_alignment_nodes(
        self,
        goals: Annotated[list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]],
                         Field(min_length=2)],
    ) -> str:
        """Create one goal alignment node per goal."""
        from .alignment import GoalAlignment, GoalAlignmentData

        states = [NodeState(GoalAlignmentData(goal=goal), commit_sha=self.state.commit_sha) for goal in goals]
        self.graph.create_nodes(self, GoalAlignment, states, 'handoff')
        return 'Created the goal alignment nodes.'
