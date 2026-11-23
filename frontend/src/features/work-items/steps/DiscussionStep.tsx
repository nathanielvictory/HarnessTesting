import { useState } from 'react';
import { Conversation } from '../Conversation';
import { nodeLabel } from '../labels';
import type { StepProps } from './types';

export function DiscussionStep({ node, done, busy, perform, alignment }: StepProps & { alignment: boolean }) {
  const [message, setMessage] = useState('');

  return <>
    <h3>{nodeLabel(node)}</h3>
    <Conversation node={node} />
    {!done && <>
      {!node.messages.length && !node.data?.draft && <p className="muted">
        {alignment ? 'Describe what you want to accomplish.' : 'Ask for a technical plan or specify what needs to change.'}
      </p>}
      <form className="stack" onSubmit={event => {
        event.preventDefault();
        if (message.trim()) {
          perform({ type: 'messages', message });
          setMessage('');
        }
      }}>
        <label>Message<textarea value={message} onChange={event => setMessage(event.target.value)} rows={3} required /></label>
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
