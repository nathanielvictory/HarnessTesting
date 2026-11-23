from collections.abc import Callable

from harness.agents.harness import AgentHarness, AgentTurn
from harness.runtime import model_settings

from .terminal import Terminal


class InteractiveAgent(AgentHarness):
    def __init__(self, model: str, terminal: Terminal, show_graph: Callable[[], None]) -> None:
        super().__init__(model, model_settings=model_settings(model))
        self.terminal = terminal
        self.show_graph = show_graph

    def run_turn(self, prompt: str, **kwargs) -> AgentTurn:
        parent = super().run_turn
        kwargs.pop("progress", None)
        return self.terminal.wait_for_agent(
            lambda progress, token: parent(prompt, **kwargs, progress=progress, cancellation_token=token),
            self.show_graph,
        )
