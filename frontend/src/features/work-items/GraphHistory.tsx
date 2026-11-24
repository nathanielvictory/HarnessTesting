import type { ReactNode } from 'react';
import { nodeLabel } from './labels';
import type { WorkItemDetail } from './types';

interface Props {
  detail: WorkItemDetail;
  selectedId?: number;
  expanded: boolean;
  selectNode: (id: number) => void;
  children?: ReactNode;
}

export function GraphHistory({ detail, selectedId, expanded, selectNode, children }: Props) {
  const nodes = new Map(detail.nodes.map(node => [node.id, node]));
  const entryId = detail.entry_node_id;
  const selectedVisit = detail.transitions.map(edge => edge.to_node_id).lastIndexOf(selectedId ?? -1);

  return <aside className="history" id="work-item-history" data-expanded={expanded} aria-label="Graph history">
    <h3>Graph history</h3>
    <ol>
      {entryId !== null && <li><button className="history-step"
        aria-current={entryId === selectedId && selectedVisit === -1 ? 'step' : undefined} onClick={() => selectNode(entryId)}>
        <strong>{nodeLabel(nodes.get(entryId))}</strong>
        <span>Entry</span>
      </button></li>}
      {detail.transitions.map((edge, index) => <li key={`${edge.from_node_id}:${edge.outbound_order}`}>
        <button className="history-step" aria-current={index === selectedVisit ? 'step' : undefined} onClick={() => selectNode(edge.to_node_id)}>
          <strong>{nodeLabel(nodes.get(edge.to_node_id))}</strong>
          <span>
            {edge.outcome.replaceAll('_', ' ')}
            {edge.data?.reviewed_commit_sha ? ` · ${edge.data.reviewed_commit_sha.slice(0, 8)}` : ''}
          </span>
        </button>
      </li>)}
    </ol>
    {children}
  </aside>;
}
