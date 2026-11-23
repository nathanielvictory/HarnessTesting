import { Activity } from '../Activity';
import { Conversation } from '../Conversation';
import type { StepProps } from './types';

export function ImplementationStep({ node, done, busy, activity, links, perform }: StepProps) {
  return <>
    <h3>Implementation</h3>
    <p className="step-description">The agent follows the approved plan in a separate Git worktree. Harness saves its changes on the work item’s branch and brings the result to you for review.</p>
    {node.branch_ref && <p className="revision"><code>{node.branch_ref}</code></p>}
    <Conversation node={node} links={links} />
    <Activity activity={activity} />
    {!done && !activity && <button className="primary" disabled={busy} onClick={() => perform({ type: 'implement' })}>
      Run implementation
    </button>}
  </>;
}
