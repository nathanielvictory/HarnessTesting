import { Conversation } from '../Conversation';
import { nodeLabel } from '../labels';
import type { StepProps } from './types';
import { StepPane } from './StepPane';
import { useNodeDraft } from './useNodeDraft';

export function DiscussionStep({ node, done, busy, links, perform, alignment }: StepProps & { alignment: boolean }) {
  const [{ text: message }, saveDraft] = useNodeDraft(node.id);

  return <StepPane title={nodeLabel(node)} followLatest actions={!done &&
    <form className="composer" onSubmit={event => {
      event.preventDefault();
      if (!busy && message.trim()) {
        perform({ type: node.conversation_started ? 'messages' : 'start', node_id: node.id, message },
          () => saveDraft({ text: '' }));
      }
    }}>
      <textarea aria-label="Message" placeholder={alignment ? 'Describe the outcome you want…' : 'Message the planning agent…'}
        value={message} onChange={event => saveDraft({ text: event.target.value })} rows={2} disabled={busy} required />
      <button className="primary" disabled={busy || !message.trim()}>Send</button>
    </form>
  }>
    <Conversation node={node} links={links} />
  </StepPane>;
}
