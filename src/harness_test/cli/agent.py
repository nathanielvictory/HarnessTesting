from collections.abc import Callable

from pydantic_ai.models.openai import OpenAIResponsesModelSettings

from harness_test.agents.harness import AgentHarness, AgentTurn

from .terminal import Terminal


class InteractiveAgent(AgentHarness):
    def __init__(self, model: str, terminal: Terminal, show_graph: Callable[[], None]) -> None:
        settings = None
        if model.startswith("openai-codex:"):
            settings = OpenAIResponsesModelSettings(openai_reasoning_effort="medium")
        super().__init__(model, model_settings=settings)
        self.terminal = terminal
        self.show_graph = show_graph

    def run_turn(self, prompt: str, **kwargs) -> AgentTurn:
        parent = super().run_turn
        return self.terminal.wait_for_agent(
            lambda progress, token: parent(prompt, **kwargs, progress=progress, cancellation_token=token),
            self.show_graph,
        )
