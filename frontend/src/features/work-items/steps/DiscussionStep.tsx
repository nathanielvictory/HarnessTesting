import { Activity } from '../Activity';
import { Conversation } from '../Conversation';
import { nodeLabel } from '../labels';
import type { StepProps } from './types';
import { useNodeDraft } from './useNodeDraft';

export function DiscussionStep({ node, done, busy, activity, links, perform, alignment }: StepProps & { alignment: boolean }) {
  const [{ text: message }, saveDraft] = useNodeDraft(node.id);

  return <>
    <h3>{nodeLabel(node)}</h3>
    <p className="step-description">
      {alignment
        ? 'Describe the outcome you want. The agent can read the project docs and code to help draft a brief. Approve the brief when it captures the goal and how you’ll know it’s met.'
        : 'The agent uses the approved brief and the same repository snapshot to propose what to change and how to verify it. Ask for adjustments before approving the plan and starting implementation.'}
    </p>
    <Conversation node={node} links={links} />
    <Activity activity={activity} />
    {!done && !activity && <>
      <form className="stack" onSubmit={event => {
        event.preventDefault();
        if (message.trim()) {
          perform({ type: 'messages', message }, () => saveDraft({ text: '' }));
        }
      }}>
        <label>Message<textarea value={message} onChange={event => saveDraft({ text: event.target.value })} rows={3} required /></label>
        <div><button className="primary" disabled={busy || !message.trim()}>Send</button></div>
      </form>
      {node.data?.draft && <div className="approval">
        <button disabled={busy} onClick={() => perform({ type: 'approve' })}>
          Approve {alignment ? 'brief' : 'plan'}
        </button>
      </div>}
    </>}
  </>;
}
