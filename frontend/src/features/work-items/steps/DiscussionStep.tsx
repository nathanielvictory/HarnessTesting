import { useState } from 'react';
import { Conversation } from '../Conversation';
import { nodeLabel } from '../labels';
import type { StepProps } from './types';

export function DiscussionStep({ node, done, busy, perform, alignment }: StepProps & { alignment: boolean }) {
  const [message, setMessage] = useState('');
  const [baseRef, setBaseRef] = useState(node.data?.base_commit ?? '');

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
        {alignment && <label>Starting Git ref
          <input value={baseRef} placeholder="HEAD" onChange={event => setBaseRef(event.target.value)} />
        </label>}
        <button disabled={busy} onClick={() => perform(alignment
          ? { type: 'approve', base_ref: baseRef || null }
          : { type: 'approve' })}>
          Approve {alignment ? 'brief' : 'plan'}
        </button>
      </div>}
    </>}
  </>;
}
