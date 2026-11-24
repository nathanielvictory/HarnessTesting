import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness.agents.harness import AgentTurn
from harness.git.repository import GitError, GitRepository
from harness.operations.review import ReviewDecision
from harness.operations.work_session import ScopedWork, WorkSession
from harness.persistence.catalog import Catalog
from harness.persistence.database import Database
from harness.persistence.graph.repository import GraphRepository
from harness.persistence.models import Node as NodeRecord
from harness.persistence.models import NodeType, WorkItemStatus


class FakeAgent:
    model = 'test'

    def __init__(self):
        self.turns = []

    def run_turn(self, prompt, **kwargs):
        if self.turns:
            return self.turns.pop(0)(kwargs['worktree'], kwargs['conversation'])
        return AgentTurn('Draft: ' + prompt, {'messages': []})


class FrontierTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.repo = root / 'project'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Frontier Test')
        self.git('config', 'user.email', 'frontier@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('commit', '--allow-empty', '-m', 'Base')
        self.repository = GitRepository(self.repo)
        self.base = self.repository.commit_sha()
        self.database = Database(root / 'state.sqlite3')
        self.addCleanup(self.database.close)
        self.database.initialize()
        self.catalog = Catalog(self.database)
        project = self.catalog.add_project('Test', str(self.repo))
        self.item = self.catalog.add_work_item(project.id, 'Frontier', base_commit=self.base)
        self.store = GraphRepository(self.database)
        self.agent = FakeAgent()
        self.work = WorkSession(self.item.id, self.store, self.repository, self.agent, root / 'worktrees', self.item.title)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def ready(self):
        return [node.id for node in self.work.graph().current_nodes()]

    def plan(self, goal_id=None):
        self.work.talk('Draft the brief', goal_id)
        plan = self.work.approve(goal_id).edge.to_node_id
        self.work.talk('Draft the plan', plan)
        return plan

    def implementation(self, goal_id):
        return self.work.approve(self.plan(goal_id)).edge.to_node_id

    def write_turn(self, filename, content, output='Done'):
        def turn(checkout, conversation):
            (checkout / filename).write_text(content)
            return AgentTurn(output, {'messages': [], 'test': filename})
        self.agent.turns.append(turn)

    def accept(self, impl_id, filename):
        self.write_turn(filename, filename)
        review = self.work.implement(impl_id).edge.to_node_id
        return self.work.review(ReviewDecision.ACCEPT, node_id=review)

    def test_independent_defaults_and_explicit_selection(self):
        self.work.approve(self.plan(), [ScopedWork('First'), ScopedWork('Second')])
        newest, oldest = self.ready()
        self.assertGreater(newest, oldest)
        self.assertEqual(self.work.talk('Default').node.id, newest)
        self.assertEqual(self.work.talk('Choose older', oldest).node.id, oldest)

    def test_ordered_pieces_and_interrupted_implementation(self):
        plan = self.plan()
        self.work.approve(plan, [ScopedWork('A'), ScopedWork('B', [0])])
        graph = self.work.graph()
        a, b = graph.node(plan).workflow['split']
        self.assertEqual(self.ready(), [a])
        self.assertEqual(graph.blockers(graph.node(b))[0]['node_id'], a)
        with self.assertRaisesRegex(ValueError, 'not ready'):
            self.work.talk('Not yet', b)
        self.assertFalse(self.accept(self.implementation(a), 'a.txt').outcome.complete)
        b_impl = self.implementation(b)
        self.write_turn('b.txt', 'unfinished', 'Need a helper.\nPREREQUISITES: ["Utility U"]')
        interrupted = self.work.implement(b_impl)
        self.assertEqual(interrupted.outcome.name, 'blocked')
        snapshot = interrupted.node.commit_sha
        resume = interrupted.edge.to_node_id
        utility, = self.ready()
        with self.assertRaisesRegex(ValueError, 'not ready'):
            self.work.implement(resume)
        self.assertFalse(self.work.graph().can_complete())
        self.assertIs(self.catalog.get_work_item(self.item.id)[1].status, WorkItemStatus.IN_PROGRESS)
        utility_impl = self.implementation(utility)

        def implement_utility(checkout, _conversation):
            self.assertFalse((checkout / 'b.txt').exists())
            (checkout / 'u.txt').write_text('u.txt')
            return AgentTurn('Utility done', {'messages': []})

        self.agent.turns.append(implement_utility)
        utility_review = self.work.implement(utility_impl).edge.to_node_id
        self.assertFalse(self.work.review(ReviewDecision.ACCEPT, node_id=utility_review).outcome.complete)
        self.assertEqual(self.ready(), [resume])

        def continue_b(checkout, conversation):
            self.assertEqual(conversation['test'], 'b.txt')
            self.assertEqual((checkout / 'b.txt').read_text(), 'unfinished')
            self.assertTrue((checkout / 'u.txt').is_file())
            self.assertTrue((checkout / 'a.txt').is_file())
            (checkout / 'b.txt').write_text('finished')
            return AgentTurn('Done', {'messages': []})

        self.agent.turns.append(continue_b)
        review = self.work.implement(resume).edge.to_node_id
        self.assertTrue(self.work.review(ReviewDecision.ACCEPT, node_id=review).outcome.complete)
        graph = self.work.graph()
        self.assertTrue(graph.scope_accepted(a))
        self.assertEqual(graph.node(b_impl).commit_sha, snapshot)
        self.assertEqual(self.repository.read_text_file(snapshot, 'b.txt'), 'unfinished')
        self.assertEqual(graph.node(b_impl).conversation['test'], 'b.txt')
        result = graph.node(graph.entry_node_id).workflow['result_commit']
        self.assertEqual(self.git('rev-parse', f'refs/harness/results/{self.item.id}'), result)
        for path, text in [('a.txt', 'a.txt'), ('u.txt', 'u.txt'), ('b.txt', 'finished')]:
            self.assertEqual(self.repository.read_text_file(result, path), text)
        self.assertEqual(self.repository.commit_sha(), self.base)
        self.assertIs(self.catalog.get_work_item(self.item.id)[1].status, WorkItemStatus.COMPLETE)

    def test_reopening_invalidates_dependents_not_independent_work(self):
        plan = self.plan()
        self.work.approve(plan, [ScopedWork('A'), ScopedWork('B'), ScopedWork('C', [1])])
        a, b, c = self.work.graph().node(plan).workflow['split']
        self.accept(self.implementation(a), 'a.txt')
        b_plan = self.plan(b)
        b_impl = self.work.approve(b_plan).edge.to_node_id
        self.accept(b_impl, 'b.txt')
        c_plan = self.plan(c)
        self.work.reopen(b_plan, 'Use a different design for B')
        graph = self.work.graph()
        self.assertTrue(graph.scope_accepted(a))
        self.assertFalse(graph.scope_accepted(b))
        self.assertEqual(graph.node(b_impl).status, 'superseded')
        self.assertEqual(graph.node(c_plan).status, 'superseded')
        replacement, = graph.current_nodes()
        self.assertEqual(replacement.node_type, NodeType.TECHNICAL_PLANNING)
        self.assertEqual(replacement.data['goal_id'], b)

    def test_cycle_rejects_and_rolls_back_entire_batch(self):
        plan = self.plan()
        before = self.work.graph()
        with self.assertRaisesRegex(ValueError, 'cycle'):
            self.work.approve(plan, [ScopedWork('A', [1]), ScopedWork('B', [0])])
        after = self.work.graph()
        self.assertEqual(before.nodes, after.nodes)
        self.assertEqual(before.history(), after.history())
        self.assertEqual(self.ready(), [plan])

    def test_conflicting_accepted_work_cannot_complete(self):
        plan = self.plan()
        self.work.approve(plan, [ScopedWork('A'), ScopedWork('B')])
        a, b = self.work.graph().node(plan).workflow['split']
        self.assertFalse(self.accept(self.implementation(a), 'shared.txt').outcome.complete)
        impl = self.implementation(b)
        self.write_turn('shared.txt', 'conflicting edit')
        review = self.work.implement(impl).edge.to_node_id
        with self.assertRaisesRegex(GitError, 'Could not integrate'):
            self.work.review(ReviewDecision.ACCEPT, node_id=review)
        self.assertEqual(self.ready(), [review])
        self.assertTrue(self.work.graph().scope_accepted(a))
        self.assertIs(self.catalog.get_work_item(self.item.id)[1].status, WorkItemStatus.IN_PROGRESS)

    def test_straight_line_and_legacy_transition_replay(self):
        plan = self.plan()
        ids = list(self.work.graph().nodes)
        with self.database.session() as session:
            for node_id in ids:
                row = session.get(NodeRecord, node_id)
                row.data = {key: value for key, value in row.data.items() if key != '_workflow'}
        self.assertEqual(self.ready(), [plan])
        impl = self.work.approve().edge.to_node_id
        self.assertEqual(self.ready(), [impl])
        self.assertTrue(self.accept(impl, 'straight.txt').outcome.complete)

    def test_empty_ready_list_is_not_completion(self):
        entry, = self.ready()
        def change(edit):
            edit.graph.node(entry).update_workflow(status='done')
        self.store.edit(self.item.id, change)
        self.assertEqual(self.ready(), [])
        self.assertFalse(self.work.graph().can_complete())
