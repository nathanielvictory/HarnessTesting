import { useState } from 'react';
import { Conversation } from './Conversation';
import { GraphHistory } from './GraphHistory';
import { nodeLabel, workItemTitle } from './labels';
import { DiscussionStep } from './steps/DiscussionStep';
import { ImplementationStep } from './steps/ImplementationStep';
import { ReviewStep } from './steps/ReviewStep';
import type { WorkItemCommand, WorkItemDetail } from './types';
import './work-item.css';

interface Props {
  detail: WorkItemDetail;
  busy: boolean;
  perform: (command: WorkItemCommand) => void;
}

export function WorkItemScreen({ detail, busy, perform }: Props) {
  const [historyId, setHistoryId] = useState<number | null>(null);
  const current = detail.nodes.find(node => node.id === detail.current_node_id);
  const historical = detail.nodes.find(node => node.id === historyId);
  const done = detail.work_item.status === 'complete';

  return <>
    <div className="item-heading">
      <h2>{workItemTitle(detail.work_item)}</h2>
      <p className="muted">{done ? 'Complete' : nodeLabel(current)}</p>
    </div>
    <div className="work-grid">
      <section className="panel">
        {historical && historical.id !== current?.id
          ? <>
            <div className="panel-heading">
              <h3>{nodeLabel(historical)}</h3>
              <button onClick={() => setHistoryId(null)}>Back to current step</button>
            </div>
            <Conversation node={historical} />
          </>
          : <CurrentStep key={current?.id} detail={detail} busy={busy} perform={perform} />}
      </section>
      <GraphHistory detail={detail} selectNode={setHistoryId} />
    </div>
  </>;
}

function CurrentStep({ detail, busy, perform }: Props) {
  const node = detail.nodes.find(node => node.id === detail.current_node_id);
  if (!node) return null;
  const done = detail.work_item.status === 'complete';
  const step = { node, done, busy, perform };

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
    case 'implementation':
      return <ImplementationStep {...step} />;
    default:
      return <>
        <h3>{nodeLabel(node)}</h3>
        <Conversation node={node} />
      </>;
  }
}
