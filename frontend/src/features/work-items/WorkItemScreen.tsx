import { useState } from 'react';
import { UsageSummary } from '../usage/UsageSummary';
import { Activity } from './Activity';
import { Conversation } from './Conversation';
import { GraphHistory } from './GraphHistory';
import { nodeLabel, workItemTitle } from './labels';
import type { RepositoryLinks } from './MessageMarkdown';
import { DiscussionStep } from './steps/DiscussionStep';
import { ImplementationStep } from './steps/ImplementationStep';
import { ReviewStep } from './steps/ReviewStep';
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
  const current = detail.nodes.find(node => node.id === detail.current_node_id);
  const historical = detail.nodes.find(node => node.id === historyId);
  const showingHistory = historical && historical.id !== current?.id;
  const done = detail.work_item.status === 'complete';
  const links = { itemId: detail.work_item.id, repositoryPath: detail.project.repository_path };

  return <>
    <div className="item-heading">
      <div>
        <h2>{workItemTitle(detail.work_item)}</h2>
        <p className="muted">{done ? 'Complete' : nodeLabel(current)}</p>
      </div>
      {!done && <button disabled={busy} onClick={() => perform({ type: 'close' })}>Mark complete</button>}
    </div>
    <UsageSummary scope="work-items" id={detail.work_item.id} busy={busy} />
    <div className="work-grid">
      <section className="panel">
        {showingHistory && <>
          <div className="panel-heading">
            <h3>{nodeLabel(historical)}</h3>
            <button onClick={() => setHistoryId(null)}>Back to current step</button>
          </div>
          <Conversation node={historical} links={links} />
          <Activity activity={activity} />
        </>}
        <div hidden={showingHistory}>
          <CurrentStep key={current?.id} detail={detail} busy={busy} activity={activity} perform={perform} links={links} />
        </div>
      </section>
      <GraphHistory detail={detail} selectNode={setHistoryId} />
    </div>
  </>;
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
    case 'implementation':
      return <ImplementationStep {...step} />;
    default:
      return <>
        <h3>{nodeLabel(node)}</h3>
        <Conversation node={node} links={links} />
        <Activity activity={activity} />
      </>;
  }
}
