from pathlib import Path

from pydantic_ai.exceptions import AgentRunError, UserError

from harness_test.git.repository import GitError, GitRepository
from harness_test.graph.state import Graph, Node
from harness_test.graph.traverser import Step
from harness_test.operations.review import ReviewDecision
from harness_test.operations.work_session import WorkSession
from harness_test.persistence.catalog import Catalog, ProjectEntry, WorkItemEntry
from harness_test.persistence.database import Database
from harness_test.persistence.graph.repository import GraphRepository
from harness_test.persistence.models import NodeAction, WorkItemStatus

from .agent import InteractiveAgent
from .terminal import Quit, Terminal


class Application:
    def __init__(self, database: Database, state_dir: Path, model: str, terminal: Terminal) -> None:
        self.catalog = Catalog(database)
        self.store = GraphRepository(database)
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
                return self.catalog.add_work_item(project.id, self.terminal.ask("Title (optional): ") or None)
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
        work = WorkSession(
            item.id, self.store, GitRepository(Path(project.repository_path)),
            InteractiveAgent(self.model, self.terminal, show_graph), self.state_dir / "worktrees", item.title,
        )
        while (node := work.graph().current_node()) is not None:
            match node.action:
                case NodeAction.GOAL_ALIGNMENT | NodeAction.TECHNICAL_PLANNING:
                    self._talk(work, node)
                case NodeAction.IMPLEMENTATION:
                    self._check_pause(work.implement())
                case NodeAction.HUMAN_REVIEW:
                    if self._review(work):
                        return
                case _:
                    self.terminal.show(f"No interactive operation is configured for {node.action}.")
                    return

    def _talk(self, work: WorkSession, node: Node) -> None:
        data = node.data or {}
        self.terminal.show(f"\n{_label(node)}")
        if data.get("draft"):
            self.terminal.show(data["draft"])
        elif node.conversation is None:
            initial = data.get("revision_note")
            if initial or node.action == NodeAction.TECHNICAL_PLANNING:
                step = work.talk(initial or "Draft the technical plan.")
                self._check_pause(step)
                self.terminal.show((step.node.data or {})["draft"])
        self.terminal.show("Type a message, or use /approve, /graph, or /quit.")
        while True:
            message = self.terminal.ask("You > ")
            match message:
                case "/quit":
                    raise Quit
                case "/graph":
                    self._show_graph(work.graph())
                case "/approve":
                    current = work.graph().current_node()
                    if not (current and (current.data or {}).get("draft")):
                        self.terminal.show("Discuss the work with the agent before approving a draft.")
                        continue
                    base_ref = None
                    if node.action == NodeAction.GOAL_ALIGNMENT:
                        base = (current.data or {}).get("base_commit") or "HEAD"
                        base_ref = self.terminal.ask(f"Starting Git ref [{base}]: ") or base
                    work.approve(base_ref)
                    return
                case "":
                    continue
                case _:
                    step = work.talk(message)
                    self._check_pause(step)
                    self.terminal.show((step.node.data or {})["draft"])

    def _review(self, work: WorkSession) -> bool:
        target = work.review_target()
        data = target.data or {}
        self.terminal.show(f"\nReview · {_label(target)}")
        if target.action == NodeAction.IMPLEMENTATION:
            self.terminal.show(f"Branch: {(target.branch_ref or '').removeprefix('refs/heads/')} · commit {target.commit_sha}")
            self.terminal.show(data.get("summary", ""))
            options = [
                ("accept", "Accept and complete the work item"),
                ("feedback", "Send feedback to the same implementation conversation"),
                ("revise", "Revise the technical plan and retry from its base"),
                ("review_earlier", "Review an earlier step"),
            ]
        else:
            self.terminal.show(data.get("approved", ""))
            options = [("revise", "Revise this step"), ("return", "Return to implementation review")]
        while True:
            choice = self.terminal.choose("Review decision", [*options, ("graph", "View graph")])
            if choice == "graph":
                self._show_graph(work.graph())
                continue
            decision = ReviewDecision(choice)
            if decision is ReviewDecision.REVIEW_EARLIER:
                options = [(str(node.id), _label(node)) for node in work.earlier_steps()]
                earlier = self.terminal.choose("Earlier step to review", options)
                work.review(decision, earlier_id=int(earlier))
            else:
                note = self.terminal.ask("What should change? ") if decision in (
                    ReviewDecision.FEEDBACK, ReviewDecision.REVISE
                ) else ""
                step = work.review(decision, note)
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
        current = graph.current_node()
        if current is not None:
            self.terminal.show(f"  Current: {_label(current)}")

    @staticmethod
    def _check_pause(step: Step) -> None:
        if step.outcome.name == "paused":
            raise Quit


def _label(node: Node) -> str:
    return f"#{node.id} {node.action.replace('_', ' ')}"
