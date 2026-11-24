from pathlib import Path

from pydantic_ai.exceptions import AgentRunError, UserError

from harness.git.repository import GitError, GitRepository
from harness.graph.state import Graph, Node
from harness.graph.traverser import Step
from harness.operations.review import ReviewDecision
from harness.operations.work_session import ScopedWork, WorkSession
from harness.persistence.catalog import Catalog, ProjectEntry, WorkItemEntry
from harness.persistence.database import Database
from harness.persistence.graph.repository import GraphRepository
from harness.persistence.models import NodeType, WorkItemStatus
from harness.persistence.usage import UsageRepository

from .agent import InteractiveAgent
from .terminal import Quit, Terminal


class Application:
    def __init__(self, database: Database, state_dir: Path, model: str, terminal: Terminal) -> None:
        self.catalog = Catalog(database)
        self.store = GraphRepository(database)
        self.usage = UsageRepository(database)
        self.state_dir = state_dir
        self.model = model
        self.terminal = terminal

    def run(self) -> None:
        while True:
            project = self._project()
            while (item := self._work_item(project)) is not None:
                try:
                    self._open(project, item)
                except (GitError, AgentRunError, UserError, ValueError, OSError) as exc:
                    self.terminal.show(f"\n{exc}")

    def _project(self) -> ProjectEntry:
        while True:
            projects = self.catalog.projects()
            selected = self.terminal.choose("Projects", [
                *((str(project.id), f"{project.name} ({project.repository_path})") for project in projects),
                ("new", "Register a project"),
            ])
            if selected != "new":
                return next(project for project in projects if str(project.id) == selected)
            name = self.terminal.ask("Project name: ")
            path = self.terminal.ask("Absolute repository path: ").strip('"')
            if not name or not Path(path).is_absolute():
                self.terminal.show("Enter a name and an absolute repository path.")
                continue
            try:
                repository = GitRepository(Path(path))
            except (GitError, OSError) as exc:
                self.terminal.show(str(exc))
                continue
            return self.catalog.add_project(name, str(repository.path))

    def _work_item(self, project: ProjectEntry) -> WorkItemEntry | None:
        status = WorkItemStatus.IN_PROGRESS
        while True:
            items = self.catalog.work_items(project.id, status)
            toggle = "Show completed items" if status is WorkItemStatus.IN_PROGRESS else "Show in-progress items"
            selected = self.terminal.choose(f"{project.name} · {status.value.replace('_', ' ')}", [
                *((str(item.id), item.title or f"Work item {item.id}") for item in items),
                ("new", "New work item"), ("toggle", toggle), ("back", "Back to projects"),
            ])
            if selected == "back":
                return None
            if selected == "new":
                title = self.terminal.ask("Title (optional): ") or None
                try:
                    base = GitRepository(Path(project.repository_path)).commit_sha()
                except (GitError, OSError) as exc:
                    self.terminal.show(str(exc))
                    continue
                return self.catalog.add_work_item(project.id, title, base_commit=base)
            if selected == "toggle":
                status = WorkItemStatus.COMPLETE if status is WorkItemStatus.IN_PROGRESS else WorkItemStatus.IN_PROGRESS
            else:
                return next(item for item in items if str(item.id) == selected)

    def _open(self, project: ProjectEntry, item: WorkItemEntry) -> None:
        def show_graph() -> None:
            self._show_graph(self.store.load(item.id))

        if item.status is WorkItemStatus.COMPLETE:
            show_graph()
            return
        agent = InteractiveAgent(self.model, self.terminal, show_graph, usage=self.usage)
        work = WorkSession(
            item.id, self.store, GitRepository(Path(project.repository_path)),
            agent, self.state_dir / "worktrees", item.title,
        )
        while True:
            graph = work.graph()
            ready = graph.current_nodes()
            if not ready:
                self._show_graph(graph)
                return
            node = ready[0]
            if len(ready) > 1:
                choice = self.terminal.choose('Ready steps (newest first)', [
                    *((str(item.id), _label(item)) for item in ready),
                    ('graph', 'View graph and blockers'), ('back', 'Back to work items'),
                ])
                if choice == 'back':
                    return
                if choice == 'graph':
                    self._show_graph(graph)
                    continue
                node = graph.node(int(choice))
            match node.node_type:
                case NodeType.GOAL_ALIGNMENT | NodeType.TECHNICAL_PLANNING:
                    self._talk(work, node)
                case NodeType.IMPLEMENTATION:
                    if node.conversation is None:
                        self._check_pause(work.start(node.id))
                    else:
                        feedback = (node.data or {}).get('feedback') or next((
                            (edge.data or {}).get('note') for edge in reversed(graph.history())
                            if edge.to_node_id == node.id and edge.outcome == 'feedback'
                        ), None)
                        self._check_pause(work.follow_up(node.id, feedback or 'Continue the interrupted implementation.'))
                case NodeType.HUMAN_REVIEW:
                    if self._review(work, node.id):
                        return
                case _:
                    self.terminal.show(f"No interactive operation is configured for {node.node_type}.")
                    return

    def _talk(self, work: WorkSession, node: Node) -> None:
        data = node.data or {}
        self.terminal.show(f"\n{_label(node)}")
        if data.get("draft"):
            self.terminal.show(data["draft"])
        elif node.conversation is None:
            initial = data.get('revision_note') or data.get('scope_brief')
            if initial or node.node_type == NodeType.TECHNICAL_PLANNING:
                step = work.start(node.id, initial or "Draft the technical plan.")
                self._check_pause(step)
                node = step.node
                self.terminal.show((step.node.data or {})["draft"])
        self.terminal.show('Type a message, or use /approve, /discover, /reopen, /graph, or /quit.')
        if node.node_type == NodeType.TECHNICAL_PLANNING:
            self.terminal.show('Use /split to approve the plan and delegate its implementation.')
        while True:
            message = self.terminal.ask("You > ")
            match message:
                case "/quit":
                    raise Quit
                case "/graph":
                    self._show_graph(work.graph())
                case '/discover':
                    work.discover(self._pieces(), node.id)
                    return
                case '/reopen':
                    work.reopen(int(self.terminal.ask('Step ID: ')), self.terminal.ask('What should change? '))
                    return
                case '/approve' | '/split':
                    current = work.graph().select(node.id)
                    if not (current and (current.data or {}).get("draft")):
                        self.terminal.show("Discuss the work with the agent before approving a draft.")
                        continue
                    work.approve(node.id, self._pieces() if message == '/split' else None)
                    return
                case "":
                    continue
                case _:
                    step = work.start(node.id, message) if node.conversation is None else work.follow_up(node.id, message)
                    self._check_pause(step)
                    node = step.node
                    self.terminal.show((step.node.data or {})["draft"])

    def _pieces(self) -> list[ScopedWork]:
        pieces = []
        while brief := self.terminal.ask('Scoped brief (blank to finish): '):
            dependencies = self.terminal.ask('Prerequisite piece numbers (1-based, comma-separated; blank for none): ')
            pieces.append(ScopedWork(brief, [int(value) - 1 for value in dependencies.split(',') if value.strip()]))
        return pieces

    def _review(self, work: WorkSession, node_id: int) -> bool:
        target = work.review_target(node_id)
        data = target.data or {}
        self.terminal.show(f"\nReview · {_label(target)}")
        if target.node_type == NodeType.IMPLEMENTATION:
            self.terminal.show(f"Branch: {(target.branch_ref or '').removeprefix('refs/heads/')} · commit {target.commit_sha}")
            self.terminal.show(data.get("summary", ""))
            options = [
                ("accept", "Accept this piece"),
                ("feedback", "Send feedback to the same implementation conversation"),
                ("revise", "Reopen implementation and retry from its base"),
                ("review_earlier", "Review an earlier step"),
            ]
        else:
            self.terminal.show(data.get("approved", ""))
            options = [("revise", "Revise this step"), ("return", "Return to implementation review")]
        while True:
            choice = self.terminal.choose('Review decision', [*options, ('graph', 'View graph'),
                                                               ('discover', 'Add scoped prerequisites')])
            if choice == 'discover':
                work.discover(self._pieces(), node_id)
                return False
            if choice == "graph":
                self._show_graph(work.graph())
                continue
            decision = ReviewDecision(choice)
            if decision is ReviewDecision.REVIEW_EARLIER:
                options = [(str(node.id), _label(node)) for node in work.earlier_steps(node_id)]
                earlier = self.terminal.choose("Earlier step to review", options)
                work.review(decision, earlier_id=int(earlier), node_id=node_id)
            else:
                note = self.terminal.ask("What should change? ") if decision in (
                    ReviewDecision.FEEDBACK, ReviewDecision.REVISE
                ) else ""
                step = work.review(decision, note, node_id=node_id)
                if step.outcome.complete:
                    self.terminal.show("Work item complete.")
                    return True
            return False

    def _show_graph(self, graph: Graph) -> None:
        if graph.entry_node_id is None:
            self.terminal.show("\nGraph has no entry yet.")
            return
        history = graph.history()
        self.terminal.show(f"\nGraph · entry {_label(graph.node(graph.entry_node_id))}")
        if len(history) > 12:
            self.terminal.show(f"  {len(history) - 12} earlier transitions omitted")
        for edge in history[-12:]:
            commit = (edge.data or {}).get("reviewed_commit_sha")
            evidence = f" @ {commit[:12]}" if commit else ""
            self.terminal.show(
                f"  {_label(graph.node(edge.from_node_id))} → {_label(graph.node(edge.to_node_id))}"
                f" ({edge.outcome}{evidence})"
            )
        for node in graph.current_nodes():
            self.terminal.show(f'  Ready: {_label(node)}')
        for node in graph.nodes.values():
            if node.status == 'pending':
                for blocker in graph.blockers(node):
                    self.terminal.show(f"  Blocked: {_label(node)} — {blocker['reason']} (#{blocker['node_id']})")

    @staticmethod
    def _check_pause(step: Step) -> None:
        if step.outcome.name == "paused":
            raise Quit


def _label(node: Node) -> str:
    brief = (node.data or {}).get('scope_brief')
    return f"#{node.id} {node.node_type.replace('_', ' ')}" + (f' · {brief}' if brief else '')
