import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from threading import Lock

from .agents.harness import AgentTurn
from .git.repository import GitRepository
from .graph.node import Node, NodeStatus
from .graph.state import Graph
from .persistence.catalog import Catalog, ProjectEntry, WorkItemEntry
from .persistence.graph.repository import GraphRepository


logger = logging.getLogger(__name__)


class WorkItemConflict(RuntimeError):
    pass


class CommandStatus(StrEnum):
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'


@dataclass
class CommandActivity:
    node_id: int
    label: str
    status: CommandStatus = CommandStatus.RUNNING
    tools: list[str] = field(default_factory=list)
    error: str | None = None


class ActiveCommands:
    def __init__(self) -> None:
        self._activity: dict[int, CommandActivity] = {}
        self._claimed: set[int] = set()
        self._guard = Lock()

    def snapshot(self, item_id: int) -> CommandActivity | None:
        with self._guard:
            activity = self._activity.get(item_id)
            return replace(activity, tools=activity.tools.copy()) if activity is not None else None

    def track(self, item_id: int, node_id: int, label: str) -> None:
        with self._guard:
            self._activity[item_id] = CommandActivity(node_id, label)

    def report_tool(self, item_id: int, tool: str) -> None:
        with self._guard:
            tools = self._activity[item_id].tools
            tools.append(tool)
            del tools[:-6]

    @contextmanager
    def claim(self, item_id: int):
        with self._guard:
            if item_id in self._claimed:
                raise WorkItemConflict('This work item is already running an operation.')
            self._claimed.add(item_id)

        outcome: tuple[CommandStatus, str | None] | None = None

        def finish(status: CommandStatus, error: str | None) -> None:
            nonlocal outcome
            outcome = status, error

        try:
            yield finish
        finally:
            with self._guard:
                if outcome is not None:
                    activity = self._activity[item_id]
                    activity.status, activity.error = outcome
                self._claimed.remove(item_id)


class Harness:
    """Work-item commands shared by HTTP and MCP."""

    def __init__(self, catalog: Catalog, graphs: GraphRepository, active: ActiveCommands) -> None:
        self.catalog = catalog
        self.graphs = graphs
        self._active = active
        self._turns = ThreadPoolExecutor(thread_name_prefix='node-turn')

    def shutdown(self) -> None:
        self._turns.shutdown()

    def register_project(self, name: str, repository_path: str) -> ProjectEntry:
        if not name.strip() or not Path(repository_path).is_absolute():
            raise ValueError("Enter a project name and an absolute Git repository path.")
        repository = GitRepository(Path(repository_path))
        return self.catalog.add_project(name.strip(), str(repository.path))

    def create_work_item(self, project_id: int, message: str, title: str | None = None) -> WorkItemEntry:
        message = message.strip()
        if not message:
            raise ValueError('Enter an opening message.')
        project = self.catalog.get_project(project_id)
        title = (title or "").strip() or None
        commit_sha = GitRepository(Path(project.repository_path)).commit_sha()
        item, node_id = self.catalog.add_work_item(project_id, title, commit_sha=commit_sha, goal=message)
        with ExitStack() as activity:
            finish = activity.enter_context(self._active.claim(item.id))
            self._queue_turn(item.id, node_id, 'Starting the node', lambda node: node.init(), activity, finish)
        return item

    def follow_up(self, item_id: int, node_id: int, message: str) -> None:
        if not message.strip():
            raise ValueError('Enter a message.')
        with ExitStack() as activity:
            finish = activity.enter_context(self._active.claim(item_id))
            node = self.graphs.load(item_id).node(node_id)
            if node.status == NodeStatus.SUPERSEDED:
                raise ValueError(f'Node {node_id} is superseded.')
            if node.state.conversation is None:
                raise ValueError('This node has no conversation yet.')
            self._queue_turn(item_id, node_id, 'Preparing a reply', lambda node: node.follow_up(message), activity, finish)

    def approve_edge(self, item_id: int, edge_id: int, data: dict[str, object] | None = None) -> None:
        with ExitStack() as activity:
            try:
                finish = activity.enter_context(self._active.claim(item_id))
            except WorkItemConflict:
                # The destination's first turn may already be running after approval was saved.
                self.graphs.load(item_id).pending_edge(edge_id)
                raise
            node_id = self.graphs.edit(item_id, lambda graph: graph.approve_edge(edge_id, data))
            if node_id is not None:
                self._queue_turn(item_id, node_id, 'Starting the node', lambda node: node.init(), activity, finish)

    def retry(self, item_id: int, node_id: int) -> None:
        with ExitStack() as activity:
            finish = activity.enter_context(self._active.claim(item_id))
            node = self.graphs.load(item_id).select(node_id)
            if node.state.conversation is not None:
                raise ValueError('This node has already started its conversation.')
            self._queue_turn(item_id, node_id, 'Starting the node', lambda node: node.init(), activity, finish)

    def _queue_turn(self, item_id: int, node_id: int, label: str, command: Callable[[Node], AgentTurn],
                    activity: ExitStack, finish: Callable[[CommandStatus, str | None], None]) -> None:
        self._active.track(item_id, node_id, label)
        # Keep the work item claimed until the turn has saved its result.
        claim = activity.pop_all()

        def run() -> None:
            with claim:
                try:
                    reply = self.graphs.edit(
                        item_id, lambda graph: command(graph.node(node_id)),
                        progress=lambda tool: self._active.report_tool(item_id, tool),
                    )
                except Exception as error:
                    logger.exception('Node %s in work item %s failed', node_id, item_id)
                    finish(CommandStatus.FAILED, str(error) or type(error).__name__)
                else:
                    if reply.paused:
                        finish(CommandStatus.FAILED, 'The model turn was interrupted.')
                    else:
                        finish(CommandStatus.DONE, None)

        try:
            self._turns.submit(run)
        except RuntimeError:
            finish(CommandStatus.FAILED, 'Could not queue the model turn.')
            claim.close()
            raise

    def rollback(self, item_id: int, node_id: int, target_id: int, note: str) -> None:
        with self._active.claim(item_id):
            self.graphs.edit(item_id, lambda graph: graph.rollback(node_id, target_id, note))

    def close_work_item(self, item_id: int) -> None:
        self.catalog.complete_work_item(item_id)
