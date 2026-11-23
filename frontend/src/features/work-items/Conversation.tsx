import { MessageMarkdown } from './MessageMarkdown';
import type { RepositoryLinks } from './MessageMarkdown';
import type { WorkNode } from './types';

export function Conversation({ node, links }: { node: WorkNode; links: RepositoryLinks }) {
  if (!node.messages.length) {
    const text = node.data?.draft || node.data?.approved || node.data?.summary;
    return text ? <MessageMarkdown text={text} links={links} nodeId={node.id} /> : null;
  }
  return <ol className="messages" aria-label="Conversation">
    {node.messages.map(({ role, text }, index) => <li key={index} className={role}>
      <strong>{role === 'user' ? 'You' : 'Agent'}</strong>
      {role === 'user' ? <p className="prose">{text}</p> : <MessageMarkdown text={text} links={links} nodeId={node.id} />}
    </li>)}
  </ol>;
}
