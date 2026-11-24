import { Conversation } from '../Conversation';
import { ImplementationChanges } from '../ImplementationChanges';
import { MessageMarkdown } from '../MessageMarkdown';
import type { WorkNode } from '../types';
import { StepPane } from './StepPane';
import type { StepProps } from './types';

interface Props extends StepProps {
  plan?: WorkNode;
  feedback?: string;
}

export function ImplementationStep({ node, done, busy, activity, links, perform, plan, feedback }: Props) {
  const paused = node.data?.paused;
  const action = paused ? 'Resume implementation' : feedback ? 'Run with feedback' : 'Run implementation';

  return <StepPane title="Implementation" activity={activity} actions={!done && !activity &&
    <button className="primary" disabled={busy} onClick={() => perform({ type: 'implement' })}>{action}</button>
  }>
    {!done && <div className="step-state">
      <h4>{activity ? 'Implementation in progress' : paused ? 'Implementation paused' : feedback ? 'Ready to apply feedback' : 'Ready to implement'}</h4>
      <p>{activity
        ? 'The agent is working in its checkout. Saved changes will be available when the run finishes.'
        : paused ? 'Resume from the saved checkout, or inspect the changes saved so far.'
          : 'Start the run to implement the approved plan and bring the saved changes to review.'}</p>
    </div>}
    {node.branch_ref && <p className="revision">Branch <code>{node.branch_ref.replace(/^refs\/heads\//, '')}</code></p>}
    {feedback && <section className="step-section">
      <h4>Review feedback</h4>
      <MessageMarkdown text={feedback} links={links} nodeId={node.id} />
    </section>}
    {plan?.data?.approved && <details className="step-disclosure">
      <summary>Approved plan</summary>
      <MessageMarkdown text={plan.data.approved} links={links} nodeId={plan.id} />
    </details>}
    {node.commit_sha && <ImplementationChanges key={node.commit_sha} itemId={links.itemId} nodeId={node.id} />}
    {node.messages.length > 0 && <details className="step-disclosure">
      <summary>Implementation conversation</summary>
      <Conversation node={node} links={links} />
    </details>}
  </StepPane>;
}
