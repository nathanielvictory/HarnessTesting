from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from pydantic_ai import Tool

    from harness.agents.harness import AgentHarness, AgentTurn

    from .state import Graph


class NodeStatus(StrEnum):
    PENDING = 'pending'
    DONE = 'done'
    SUPERSEDED = 'superseded'


@dataclass(kw_only=True)
class NodeData:
    base_commit: str | None = None
    summary: str | None = None


@dataclass
class NodeState[D: NodeData]:
    data: D
    id: int | None = None
    status: NodeStatus = NodeStatus.PENDING
    model: str | None = None
    conversation: dict[str, Any] | None = None
    branch_ref: str | None = None
    commit_sha: str | None = None


class Node[D: NodeData](ABC):
    saves_changes = False
    data_type: type[D]

    def __init__(self, state: NodeState[D], graph: Graph, agent: AgentHarness) -> None:
        self.state = state
        self.graph = graph
        self.agent = agent

    @property
    def id(self) -> int:
        if self.state.id is None:
            raise ValueError('This node has no saved ID yet.')
        return self.state.id

    @property
    @abstractmethod
    def node_type(self) -> str:
        ...

    @property
    def status(self) -> NodeStatus:
        return self.state.status

    def update_data(self, changes: dict[str, object]) -> None:
        data = asdict(self.state.data)
        unknown = changes.keys() - data.keys()
        if unknown:
            raise ValueError(f'Unknown node data fields: {", ".join(sorted(unknown))}.')
        self.state.data = TypeAdapter(self.data_type).validate_python({**data, **changes})

    def init(self, message: str = '') -> AgentTurn:
        if self.state.conversation is not None:
            raise ValueError('This node already has a conversation. Send a follow-up instead.')
        if not self.graph.is_ready(self):
            raise ValueError(f'Node {self.id} is not ready.')
        instructions, prompt = self.initial_prompt(message.strip())
        return self._run(prompt, instructions=instructions)

    def follow_up(self, message: str) -> AgentTurn:
        if not message.strip():
            raise ValueError('Enter a message.')
        if self.state.conversation is None:
            raise ValueError('Start this node before sending a follow-up.')
        return self._run(message.strip())

    def _run(self, prompt: str, *, instructions: str | None = None) -> AgentTurn:
        agent = self.agent
        state = self.state
        workspace = self.graph.workspace
        checkout, state.branch_ref, base = workspace.prepare(
            self.id, state.branch_ref, state.commit_sha or state.data.base_commit or self.graph.base_commit,
        )
        if state.commit_sha is None:
            state.data.base_commit = base
        reply = agent.run_turn(
            prompt, instructions=instructions, model=agent.model, conversation=state.conversation,
            worktree=checkout, node_id=self.id, progress=self.graph.progress,
            tools=self.model_tools(),
        )
        if self.saves_changes:
            state.commit_sha = workspace.save(checkout)
        state.model = agent.model
        state.conversation = reply.conversation
        return reply

    def model_tools(self) -> tuple[str | Tool[None], ...]:
        return ()

    def initial_prompt(self, message: str) -> tuple[str, str]:
        return '', message
