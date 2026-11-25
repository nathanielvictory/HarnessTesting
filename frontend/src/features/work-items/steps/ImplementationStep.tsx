import { Conversation } from '../Conversation';
import { ImplementationChanges } from '../ImplementationChanges';
import { MessageMarkdown } from '../MessageMarkdown';
import type { WorkNode } from '../types';
import { StepPane } from './StepPane';
import type { StepProps } from './types';
import { useNodeDraft } from './useNodeDraft';

interface Props extends StepProps {
  plan?: WorkNode;
  feedback?: string;
}

export function ImplementationStep({ node, done, busy, links, perform, plan, feedback }: Props) {
  const [{ text: message }, saveDraft] = useNodeDraft(node.id);
  const paused = node.data?.paused;
  const action = paused ? 'Resume implementation' : feedback ? 'Run with feedback' : 'Run implementation';
  const followUp = node.conversation_started && !paused && (!feedback || !!node.branch_ref);

  return <StepPane title="Implementation" actions={!done && (followUp ?
    <form className="composer" onSubmit={event => {
      event.preventDefault();
      if (!busy && message.trim()) perform({ type: 'messages', node_id: node.id, message }, () => saveDraft({ text: '' }));
    }}>
      <textarea aria-label="Message" placeholder="Message the implementation agent…" rows={2}
        value={message} onChange={event => saveDraft({ text: event.target.value })} disabled={busy} required />
      <button className="primary" disabled={busy || !message.trim()}>Send</button>
    </form> :
    <button className="primary" disabled={busy} onClick={() => perform(node.conversation_started
      ? { type: 'messages', node_id: node.id, message: feedback || 'Continue the interrupted implementation.' }
      : { type: 'start', node_id: node.id })}>{action}</button>
  )}>
    {!done && !busy && !node.pending_transition && !followUp && <div className="step-state">
      <h4>{paused ? 'Implementation paused' : feedback ? 'Ready to apply feedback' : 'Ready to implement'}</h4>
      <p>{paused ? 'Resume from the saved checkout, or inspect the changes saved so far.'
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
