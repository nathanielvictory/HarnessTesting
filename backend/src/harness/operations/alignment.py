from harness.agents.harness import AgentHarness, AgentProfile
from harness.graph.state import Node
from harness.graph.traverser import Outcome


PROFILE = AgentProfile(instructions=(
    "Help the user agree on the outcome of a work item. Ask a focused question when necessary. "
    "When the intent is clear, answer with a concise proposed brief covering the outcome, "
    "constraints, and how the user will recognize success. Leave technical implementation to planning."
))


class GoalAlignment:
    def __init__(self, agents: AgentHarness) -> None:
        self.agents = agents

    def talk(self, node: Node, message: str) -> Outcome:
        data = node.data or {}
        if node.conversation is None and data.get("previous_brief"):
            message = f"Previous brief\n{data['previous_brief']}\n\nRevision request\n{message}"
        model = self.agents.model
        result = self.agents.run_turn(message, profile=PROFILE, model=model, conversation=node.conversation)
        node.model = model
        node.conversation = result.conversation
        if result.paused:
            return Outcome("paused")
        node.data = {**data, "draft": result.output}
        return Outcome("reply")
