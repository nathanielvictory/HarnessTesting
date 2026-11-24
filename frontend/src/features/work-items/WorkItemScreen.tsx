import { useState } from 'react';
import { Conversation } from './Conversation';
import { GraphHistory } from './GraphHistory';
import { ImplementationChanges } from './ImplementationChanges';
import { nodeLabel } from './labels';
import type { RepositoryLinks } from './MessageMarkdown';
import { DiscussionStep } from './steps/DiscussionStep';
import { ImplementationStep } from './steps/ImplementationStep';
import { ReviewStep } from './steps/ReviewStep';
import { StepPane } from './steps/StepPane';
import type { PerformCommand } from './steps/types';
import type { WorkItemActivity, WorkItemDetail } from './types';
import './work-item.css';

interface Props {
  detail: WorkItemDetail;
  busy: boolean;
  activity: WorkItemActivity | null;
  perform: PerformCommand;
}

export function WorkItemScreen({ detail, busy, activity, perform }: Props) {
  const [historyId, setHistoryId] = useState<number | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const current = detail.nodes.find(node => node.id === detail.current_node_id);
  const historical = detail.nodes.find(node => node.id === historyId);
  const showingHistory = historical && historical.id !== current?.id;
  const reviewedImplementation = historical?.node_type === 'human_review' ? detail.nodes.find(node =>
    node.id === historical.data?.target_id && node.node_type === 'implementation',
  ) : undefined;
  const selectedId = historical?.id ?? current?.id;
  const links = { itemId: detail.work_item.id, repositoryPath: detail.project.repository_path };

  return <div className="work-grid">
    <button className="history-toggle" aria-expanded={historyOpen} aria-controls="work-item-history"
      onClick={() => setHistoryOpen(open => !open)}>
      {historyOpen ? 'Hide graph history' : 'Graph history'}
    </button>
    <div className="step-slot">
      {showingHistory && <StepPane key={historical.id} title={nodeLabel(historical)} activity={activity}
        onReturn={() => setHistoryId(null)}>
        <Conversation node={historical} links={links} />
        {historical.node_type === 'implementation' && historical.commit_sha &&
          <ImplementationChanges key={historical.commit_sha} itemId={links.itemId} nodeId={historical.id} />}
        {reviewedImplementation && (historical.data?.last_decision?.reviewed_commit_sha || reviewedImplementation.commit_sha) &&
          <ImplementationChanges itemId={links.itemId} nodeId={historical.id} />}
      </StepPane>}
      <div className="step-slot" hidden={showingHistory}>
        <CurrentStep key={current?.id} detail={detail} busy={busy} activity={activity} perform={perform} links={links} />
      </div>
    </div>
    <GraphHistory detail={detail} selectedId={selectedId} expanded={historyOpen} selectNode={id => {
      setHistoryId(id);
      setHistoryOpen(false);
    }} />
  </div>;
}

function CurrentStep({ detail, busy, activity, perform, links }: Props & { links: RepositoryLinks }) {
  const node = detail.nodes.find(node => node.id === detail.current_node_id);
  if (!node) return null;
  const done = detail.work_item.status === 'complete';
  const step = { node, done, busy, activity, perform, links };

  const review = detail.review;
  if (review) {
    const target = detail.nodes.find(candidate => candidate.id === review.target_id);
    if (!target) return <p role="alert">The step under review could not be found.</p>;
    const earlier = review.earlier_ids.map(id => ({
      id,
      label: nodeLabel(detail.nodes.find(candidate => candidate.id === id)),
    }));
    return <ReviewStep {...step} target={target} earlier={earlier} />;
  }
  switch (node.node_type) {
    case 'goal_alignment':
    case 'technical_planning':
      return <DiscussionStep {...step} alignment={node.node_type === 'goal_alignment'} />;
    case 'implementation': {
      const plan = detail.nodes.find(candidate => candidate.id === node.data?.plan_id);
      const incoming = detail.transitions.at(-1);
      const feedback = incoming?.to_node_id === node.id && incoming.outcome === 'feedback' ? incoming.data?.note : undefined;
      return <ImplementationStep {...step} plan={plan} feedback={typeof feedback === 'string' ? feedback : undefined} />;
    }
    default:
      return <StepPane title={nodeLabel(node)} activity={activity} followLatest>
        <Conversation node={node} links={links} />
      </StepPane>;
  }
}
