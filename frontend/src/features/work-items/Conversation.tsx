import type { WorkNode } from './types';

export function Conversation({ node }: { node: WorkNode }) {
  if (!node.messages.length) {
    const text = node.data?.draft || node.data?.approved || node.data?.summary;
    return text ? <p className="prose">{text}</p> : null;
  }
  return <ol className="messages" aria-label="Conversation">
    {node.messages.map(({ role, text }, index) => <li key={index} className={role}>
      <strong>{role === 'user' ? 'You' : 'Agent'}</strong>
      <p className="prose">{text}</p>
    </li>)}
  </ol>;
}
