import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from harness.agents.harness import AgentTurn
from harness.application import ActiveCommands, Harness
from harness.git.repository import GitRepository
from harness.operations.review import ReviewDecision
from harness.graph.node import NodeState, NodeStatus
from harness.graph.state import EdgeStatus
from harness.operations.implementation import Implementation, ImplementationData
from harness.operations.planning import TechnicalPlanning
from harness.persistence.catalog import Catalog
from harness.persistence.database import Database
from harness.persistence.graph.repository import GraphRepository
from harness.persistence.models import Node as NodeRecord
from harness.persistence.models import WorkItemStatus


class FakeAgent:
    model = 'test'

    def __init__(self):
        self.turns = []
        self.prompts = []
        self.turn_options = []

    def run_turn(self, prompt, **kwargs):
        self.prompts.append(prompt)
        self.turn_options.append(kwargs)
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
        self.agent = FakeAgent()
        graphs = GraphRepository(self.database, self.agent, root / 'worktrees')
        self.harness = Harness(Catalog(self.database), graphs, ActiveCommands())
        project = self.harness.register_project('Test', str(self.repo))
        self.item = self.harness.create_work_item(project.id, 'Frontier')

    def graph(self):
        return self.harness.graphs.load(self.item.id)

    def status(self):
        return self.harness.catalog.get_work_item(self.item.id)[1].status

    def pending(self, node_id):
        return [edge for edge in self.graph().edges
                if edge.from_node_id == node_id and edge.status == EdgeStatus.PENDING]

    def approve(self, node_id, outcome):
        edge, = [edge for edge in self.pending(node_id) if edge.outcome == outcome]
        self.harness.approve_edge(self.item.id, edge.id)
        return edge.to_node_id

    def add_two_implementations(self, plan):
        def record_reply(node, reply):
            node.state.data.summary = reply.output
            for _ in range(2):
                node.graph.connect(node, Implementation, NodeState(ImplementationData(
                    brief=node.state.data.brief, plan=reply.output,
                )), 'handoff')

        with patch.object(TechnicalPlanning, 'record_reply', record_reply):
            self.harness.start(self.item.id, plan, 'Try both implementations')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def ready(self):
        return [node.id for node in self.graph().current_nodes()]

    def plan(self, goal_id=None):
        if goal_id is None:
            goal_id, = self.ready()
        self.harness.start(self.item.id, goal_id, 'Draft the brief')
        plan = self.approve(goal_id, 'handoff')
        self.harness.start(self.item.id, plan, 'Draft the plan')
        return plan

    def implementation(self, goal_id):
        return self.approve(self.plan(goal_id), 'handoff')

    def write_turn(self, filename, content, output='Done'):
        def turn(checkout, conversation):
            (checkout / filename).write_text(content)
            return AgentTurn(output, {'messages': [], 'test': filename})
        self.agent.turns.append(turn)

    def test_two_edges_exist_before_either_is_approved(self):
        goal, = self.ready()
        self.harness.start(self.item.id, goal, 'Draft the brief')
        plan = self.approve(goal, 'handoff')
        self.add_two_implementations(plan)

        edges = self.pending(plan)
        self.assertEqual(len(edges), 2)
        self.assertEqual(self.ready(), [plan])
        self.assertTrue(all(isinstance(edge.target, Implementation) for edge in edges))
        self.assertTrue(all(isinstance(edge.target.state.data, ImplementationData) for edge in edges))
        self.assertTrue(all(edge.id is not None and edge.to_node_id for edge in edges))
        self.assertNotIn('tools', self.agent.turn_options[-1])

        first, second = edges
        with self.assertRaisesRegex(ValueError, 'not ready'):
            self.harness.start(self.item.id, second.to_node_id)
        self.harness.approve_edge(self.item.id, first.id)
        self.assertEqual(self.ready(), [first.to_node_id])
        self.assertEqual([edge.id for edge in self.pending(plan)], [second.id])
        self.harness.approve_edge(self.item.id, second.id)
        self.assertEqual(self.ready(), [second.to_node_id, first.to_node_id])

    def test_start_and_follow_up_are_distinct(self):
        goal, = self.ready()
        with self.assertRaisesRegex(ValueError, 'Start this node'):
            self.harness.follow_up(self.item.id, goal, 'Too early')
        self.harness.start(self.item.id, goal, 'Draft the brief')
        with self.assertRaisesRegex(ValueError, 'already has a conversation'):
            self.harness.start(self.item.id, goal)
        plan = self.approve(goal, 'handoff')
        self.harness.start(self.item.id, plan, 'Draft the plan')
        self.assertIn('Approved brief', self.agent.prompts[-1])
        first, = self.pending(plan)
        previous_plan = first.target.state.data.plan
        self.harness.follow_up(self.item.id, plan, 'Explain the plan')
        first, second = self.pending(plan)
        self.assertEqual(first.target.state.data.plan, previous_plan)
        self.assertIn('Explain the plan', second.target.state.data.plan)
        self.assertEqual(self.agent.prompts[-1], 'Explain the plan')
        self.assertEqual(self.ready(), [plan])

    def test_implementation_feedback_follows_up_on_saved_conversation(self):
        impl = self.implementation(None)
        self.write_turn('implementation.txt', 'first version')
        self.harness.start(self.item.id, impl)
        self.assertEqual(self.ready(), [impl])
        self.assertEqual(self.pending(impl)[0].outcome, 'review')
        review = self.approve(impl, 'review')
        self.assertIn('Approved technical plan', self.agent.prompts[-1])
        self.harness.review(self.item.id, review, ReviewDecision.FEEDBACK, 'Adjust the result')
        self.assertEqual(self.ready(), [review])
        self.assertEqual(self.pending(review)[0].outcome, 'feedback')
        follow_up = self.approve(review, 'feedback')
        with self.assertRaisesRegex(ValueError, 'already has a conversation'):
            self.harness.start(self.item.id, follow_up)
        self.write_turn('implementation.txt', 'updated version')
        self.harness.follow_up(self.item.id, follow_up, 'Adjust the result')
        next_review = self.approve(follow_up, 'review')
        self.assertEqual(self.agent.prompts[-1], 'Adjust the result')
        self.assertEqual(self.graph().node(next_review).state.data.target_id, follow_up)

    def test_approval_rolls_back_to_the_existing_node(self):
        impl = self.implementation(None)
        self.write_turn('implementation.txt', 'first version')
        self.harness.start(self.item.id, impl)
        review = self.approve(impl, 'review')
        before = self.graph()
        saved = before.node(impl).state

        self.harness.review(self.item.id, review, ReviewDecision.REVISE, 'Adjust the implementation')
        pending = self.graph()
        edge, = self.pending(review)
        self.assertEqual(self.ready(), [review])
        self.assertEqual(len(pending.nodes), len(before.nodes))
        self.assertEqual(edge.to_node_id, impl)
        self.assertEqual(edge.status, EdgeStatus.PENDING)

        self.assertEqual(self.approve(review, 'rollback'), impl)
        after = self.graph()
        self.assertEqual({node.id for node in after.nodes}, {node.id for node in before.nodes})
        self.assertEqual(self.ready(), [impl])
        self.assertEqual(after.node(review).status, NodeStatus.SUPERSEDED)
        resumed = after.node(impl).state
        self.assertEqual(resumed.conversation, saved.conversation)
        self.assertEqual(resumed.branch_ref, saved.branch_ref)
        self.assertEqual(resumed.commit_sha, saved.commit_sha)

        def continue_implementation(checkout, conversation):
            self.assertEqual(conversation, saved.conversation)
            self.assertEqual((checkout / 'implementation.txt').read_text(), 'first version')
            return AgentTurn('Adjusted', conversation)

        self.agent.turns.append(continue_implementation)
        self.harness.follow_up(self.item.id, impl, 'Adjust the implementation')
        plan, = [node.id for node in after.predecessors(after.node(impl)) if isinstance(node, TechnicalPlanning)]
        self.harness.rollback(self.item.id, impl, plan, 'Revisit the plan')
        self.assertEqual(self.approve(impl, 'rollback'), plan)
        self.assertEqual(self.ready(), [plan])

    def test_work_item_status_and_edge_approval_are_independent(self):
        goal, = self.ready()
        self.harness.start(self.item.id, goal, 'Draft the brief')
        edge, = self.pending(goal)
        self.harness.close_work_item(self.item.id)
        self.assertIs(self.status(), WorkItemStatus.COMPLETE)
        self.assertEqual(self.ready(), [goal])
        self.assertEqual([item.id for item in self.pending(goal)], [edge.id])
        self.harness.approve_edge(self.item.id, edge.id)
        self.assertEqual(self.ready(), [edge.to_node_id])
        self.assertIs(self.status(), WorkItemStatus.COMPLETE)

    def test_saved_legacy_nodes_get_typed_data(self):
        plan = self.plan()
        graph = self.graph()
        goal = graph.entry_node_id
        with self.database.session() as session:
            old_goal = session.get(NodeRecord, goal)
            old_goal.data = {'base_commit': self.base, 'approved': 'An older brief'}
            old_goal.status = None
            old_plan = session.get(NodeRecord, plan)
            old_plan.data = {'goal_id': goal, 'base_commit': self.base}
            old_plan.status = None

        node = self.graph().node(plan)
        self.assertIsInstance(node, TechnicalPlanning)
        self.assertEqual(node.state.data.brief, 'An older brief')
        self.assertEqual(self.ready(), [plan])
        self.harness.follow_up(self.item.id, plan, 'Continue planning')
        self.assertEqual(self.pending(plan)[-1].target.state.data.brief, 'An older brief')
