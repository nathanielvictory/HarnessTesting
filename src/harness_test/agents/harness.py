import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, CancellationToken, capture_run_conversation
from pydantic_ai.capabilities import AgentCapability, LocalWorkspace, WindowsWorkspace
from pydantic_ai.conversation import ConversationTypeAdapter
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import FunctionToolCallEvent
from pydantic_ai.settings import ModelSettings
from pydantic_ai_harness.file_system import FileSystem


@dataclass(frozen=True)
class AgentProfile:
    instructions: str
    file_tools: tuple[str, ...] = ()
    capabilities: tuple[AgentCapability[None], ...] = ()


@dataclass(frozen=True)
class AgentTurn:
    output: str
    conversation: dict[str, Any] | None
    paused: bool = False


class AgentHarness:
    def __init__(self, model: str, *, model_settings: ModelSettings | None = None) -> None:
        self.model = model
        self.model_settings = model_settings

    def run_turn(
        self,
        prompt: str,
        *,
        profile: AgentProfile,
        model: str | None = None,
        conversation: dict[str, Any] | None = None,
        worktree: Path | None = None,
        progress: Callable[[str], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> AgentTurn:
        prior = ConversationTypeAdapter.validate_python(conversation) if conversation is not None else None
        capabilities = list(profile.capabilities)
        if profile.file_tools:
            if worktree is None:
                raise ValueError("A profile with file tools needs a workspace path")
            workspace = WindowsWorkspace(worktree) if sys.platform == "win32" else LocalWorkspace(worktree)
            capabilities.extend([
                workspace,
                FileSystem(
                    tools=profile.file_tools,
                    denied_patterns=["**/.git", "**/.env", "**/.env.*"],
                ),
            ])
        async def report(_context, events):
            async for event in events:
                if isinstance(event, FunctionToolCallEvent) and event.args_valid and progress is not None:
                    progress(event.part.tool_name)

        agent = Agent(
            model or self.model, instructions=profile.instructions,
            capabilities=capabilities, model_settings=self.model_settings,
        )
        with capture_run_conversation() as captured:
            try:
                result = agent.run_sync(
                    prompt, conversation=prior, cancellation_token=cancellation_token,
                    event_stream_handler=report if progress is not None else None,
                )
            except RunCancelled:
                state = captured.conversation
                saved = ConversationTypeAdapter.dump_python(state, mode="json") if state else conversation
                return AgentTurn("", saved, paused=True)
        return AgentTurn(
            output=result.output,
            conversation=ConversationTypeAdapter.dump_python(result.conversation, mode="json"),
        )
