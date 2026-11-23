import { nodeLabel } from './labels';
import type { WorkItemDetail } from './types';

interface Props {
  detail: WorkItemDetail;
  selectNode: (id: number) => void;
}

export function GraphHistory({ detail, selectNode }: Props) {
  const nodes = new Map(detail.nodes.map(node => [node.id, node]));
  const entryId = detail.entry_node_id;

  return <aside className="panel history" aria-label="Graph history">
    <h3>Graph history</h3>
    {entryId !== null && <button className="history-step" onClick={() => selectNode(entryId)}>
      <strong>{nodeLabel(nodes.get(entryId))}</strong>
      <span>Entry</span>
    </button>}
    <ol>
      {detail.transitions.map(edge => <li key={`${edge.from_node_id}:${edge.outbound_order}`}>
        <button className="history-step" onClick={() => selectNode(edge.to_node_id)}>
          <strong>{nodeLabel(nodes.get(edge.to_node_id))}</strong>
          <span>
            {edge.outcome.replaceAll('_', ' ')}
            {edge.data?.reviewed_commit_sha ? ` · ${edge.data.reviewed_commit_sha.slice(0, 8)}` : ''}
          </span>
        </button>
      </li>)}
    </ol>
  </aside>;
}
