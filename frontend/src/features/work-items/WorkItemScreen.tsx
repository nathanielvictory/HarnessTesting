import { useState } from 'react';
import { Conversation } from './Conversation';
import { GraphHistory } from './GraphHistory';
import { ImplementationChanges } from './ImplementationChanges';
import { nodeLabel } from './labels';
import type { RepositoryLinks } from './MessageMarkdown';
import { DiscussionStep } from './steps/DiscussionStep';
import { ImplementationStep } from './steps/ImplementationStep';
import { ReviewStep } from './steps/ReviewStep';
import { StepPane } from './steps/StepPane';
import type { PerformCommand } from './steps/types';
import type { ScopedWork, WorkItemDetail, WorkNode } from './types';
import './work-item.css';

interface Props {
  detail: WorkItemDetail;
  busy: boolean;
  perform: PerformCommand;
}

export function WorkItemScreen({ detail, busy, perform }: Props) {
  const [historyId, setHistoryId] = useState<number | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [readySelection, setReadySelection] = useState<number | null>(null);
  const done = detail.work_item.status === 'complete';
  const readyIds = detail.ready_node_ids;
  const currentId = done ? detail.transitions.at(-1)?.to_node_id ?? detail.entry_node_id
    : readySelection !== null && readyIds.includes(readySelection) ? readySelection : readyIds.length === 1 ? readyIds[0] : undefined;
  const current = detail.nodes.find(node => node.id === currentId);
  const historical = detail.nodes.find(node => node.id === historyId);
  const showingHistory = historical && historical.id !== current?.id;
  const reviewedImplementation = historical?.node_type === 'human_review' ? detail.nodes.find(node =>
    node.id === historical.data?.target_id && node.node_type === 'implementation',
  ) : undefined;
  const selectedNode = historical ?? current;
  const links = { itemId: detail.work_item.id, repositoryPath: detail.project.repository_path };

  return <div className="work-grid">
    <button className="history-toggle" aria-expanded={historyOpen} aria-controls="work-item-history"
      onClick={() => setHistoryOpen(open => !open)}>
      {historyOpen ? 'Hide graph history' : 'Graph history'}
    </button>
    <div className="step-slot">
      {!done && detail.ready_node_ids.length > 1 && <label className="ready-step">Ready step <select disabled={busy}
        value={currentId ?? ''} onChange={event => { setReadySelection(Number(event.target.value)); setHistoryId(null); }}>
        <option value="" disabled>Choose a ready step</option>
        {detail.ready_node_ids.map(id => <option key={id} value={id}>{stepLabel(detail, id)}</option>)}
      </select></label>}
      {showingHistory && <StepPane key={historical.id} title={nodeLabel(historical)}
        onReturn={() => setHistoryId(null)}>
        <Conversation node={historical} links={links} />
        {historical.node_type === 'implementation' && historical.commit_sha &&
          <ImplementationChanges key={historical.commit_sha} itemId={links.itemId} nodeId={historical.id} />}
        {reviewedImplementation && (historical.data?.last_decision?.reviewed_commit_sha || reviewedImplementation.commit_sha) &&
          <ImplementationChanges itemId={links.itemId} nodeId={historical.id} />}
      </StepPane>}
      <div className="step-slot" hidden={showingHistory}>
        {current ? <CurrentStep key={current.id} node={current} detail={detail} busy={busy} links={links} perform={perform} /> :
          <p className="empty">{readyIds.length ? 'Choose the step you want to work on.'
            : 'No steps are ready. Review the blockers and graph history.'}</p>}
      </div>
      {!done && selectedNode?.pending_transition && <TransitionApproval node={selectedNode} busy={busy} perform={perform} />}
    </div>
    <GraphHistory detail={detail} selectedId={selectedNode?.id} expanded={historyOpen} selectNode={id => {
      if (readyIds.includes(id)) {
        setReadySelection(id);
        setHistoryId(null);
      } else {
        setHistoryId(id);
      }
      setHistoryOpen(false);
    }}>
      {!done && Object.keys(detail.blocked).length > 0 && <section className="frontier-sidebar" aria-label="Blocked steps">
        <h3>Blocked steps</h3>
        <ul>{Object.entries(detail.blocked).map(([id, blockers]) => <li key={id}>
          <button onClick={() => { setHistoryId(Number(id)); setHistoryOpen(false); }}>{stepLabel(detail, Number(id))}</button>
          {blockers.map(({ node_id, reason }) => <div key={`${node_id}:${reason}`} className="muted">{reason}: {stepLabel(detail, node_id)}</div>)}
        </li>)}</ul>
      </section>}
      {!done && selectedNode && <div className="frontier-sidebar">
        {!showingHistory && current && <ScopeForm key={current.id} node={current} busy={busy} perform={perform} />}
        <ReopenForm key={selectedNode.id} node={selectedNode} busy={busy} perform={perform} />
      </div>}
      {done && <p className="frontier-sidebar muted">{detail.result_commit ? <>Result <code>{detail.result_commit.slice(0, 8)}</code></> : 'Closed without an integrated result.'}</p>}
    </GraphHistory>
  </div>;
}

function stepLabel(detail: WorkItemDetail, id: number) {
  const node = detail.nodes.find(candidate => candidate.id === id);
  return `#${id} ${nodeLabel(node)}${node?.scope_brief ? ` · ${node.scope_brief}` : ''}`;
}

function TransitionApproval({ node, busy, perform }: Pick<Props, 'busy' | 'perform'> & { node: WorkNode }) {
  const request = node.pending_transition;
  if (!request) return null;
  const destinations = request.edges.map(edge => {
    const destination = edge.scope_brief || nodeLabel(edge);
    return `${edge.outcome.replaceAll('_', ' ')} → ${destination}${edge.note ? ` · ${edge.note}` : ''}`;
  });
  return <div className="step-footer transition-approval">
    {destinations.length > 1 ? <details>
      <summary>{destinations.length} requested transitions</summary>
      <ul>{destinations.map((destination, index) => <li key={index}>{destination}</li>)}</ul>
    </details> : <span>{request.accept ? 'Accept this piece' : destinations[0]}</span>}
    <button className="primary" disabled={busy} onClick={() => perform({
      type: 'approve', node_id: node.id, request_id: request.id,
    })}>{request.accept ? 'Approve acceptance' : 'Approve transition'}</button>
  </div>;
}

function ScopeForm({ node, busy, perform }: Pick<Props, 'busy' | 'perform'> & { node: WorkNode }) {
  const [pieces, setPieces] = useState([{ brief: '', dependencies: '' }]);
  const [split, setSplit] = useState(false);
  const [error, setError] = useState('');
  return <details>
    <summary>Add scoped work</summary>
    <form className="stack" onSubmit={event => {
      event.preventDefault();
      const batch: ScopedWork[] = pieces.map(piece => ({
        brief: piece.brief.trim(),
        depends_on: piece.dependencies.trim() ? piece.dependencies.split(',').map(value => Number(value) - 1) : [],
      }));
      if (batch.some(piece => !piece.brief || piece.depends_on.some(index => !Number.isInteger(index) || index < 0 || index >= batch.length))) {
        setError('Enter a scoped brief and valid prerequisite piece numbers.');
        return;
      }
      setError('');
      perform(split ? { type: 'delegate', node_id: node.id, pieces: batch }
        : { type: 'discover', node_id: node.id, pieces: batch });
    }}>
      {pieces.map((piece, index) => <fieldset key={index} disabled={busy}>
        <legend>Piece {index + 1}</legend>
        <label>Scoped brief <textarea required value={piece.brief} onChange={event => {
          setPieces(rows => rows.map((row, i) => i === index ? { ...row, brief: event.target.value } : row));
        }} /></label>
        <label>Prerequisite piece numbers (comma-separated) <input value={piece.dependencies} onChange={event => {
          setPieces(rows => rows.map((row, i) => i === index ? { ...row, dependencies: event.target.value } : row));
        }} /></label>
      </fieldset>)}
      <button type="button" disabled={busy} onClick={() => setPieces(rows => [...rows, { brief: '', dependencies: '' }])}>Add another piece</button>
      {pieces.length > 1 && <button type="button" disabled={busy} onClick={() => setPieces(rows => rows.slice(0, -1))}>Remove last piece</button>}
      {node.node_type === 'technical_planning' && node.data?.draft && <label>
        <input type="checkbox" checked={split} disabled={busy} onChange={event => setSplit(event.target.checked)} />
        Delegate this plan’s implementation to these pieces
      </label>}
      {error && <p role="alert">{error}</p>}
      <button disabled={busy}>{split ? 'Request delegation' : 'Request prerequisites'}</button>
    </form>
  </details>;
}

function ReopenForm({ node, busy, perform }: Pick<Props, 'busy' | 'perform'> & { node: WorkNode }) {
  const [note, setNote] = useState('');
  if (node.status === 'superseded' || node.node_type === 'human_review') return null;
  return <details>
    <summary>Reopen this step</summary>
    <form className="stack" onSubmit={event => {
      event.preventDefault();
      if (note.trim()) perform({ type: 'reopen', node_id: node.id, note });
    }}>
      <label>What should change? <textarea required disabled={busy} value={note} onChange={event => setNote(event.target.value)} /></label>
      <button disabled={busy || !note.trim()}>Request reopening</button>
    </form>
  </details>;
}

function CurrentStep({ node, detail, busy, perform, links }: Props & { links: RepositoryLinks; node: WorkNode }) {
  const done = detail.work_item.status === 'complete';
  const step = { node, done, busy, perform, links };

  const review = detail.reviews[node.id];
  const targetId = review?.target_id ?? node.data?.target_id;
  if (node.node_type === 'human_review' && targetId !== undefined) {
    const target = detail.nodes.find(candidate => candidate.id === targetId);
    if (!target) return <p role="alert">The step under review could not be found.</p>;
    const earlier = (review?.earlier_ids ?? []).map(id => ({
      id,
      label: nodeLabel(detail.nodes.find(candidate => candidate.id === id)),
    }));
    return <ReviewStep {...step} target={target} earlier={earlier} />;
  }
  switch (node.node_type) {
    case 'goal_alignment':
    case 'technical_planning':
      return <DiscussionStep {...step} alignment={node.node_type === 'goal_alignment'} />;
    case 'implementation': {
      const plan = detail.nodes.find(candidate => candidate.id === node.data?.plan_id);
      const incoming = detail.transitions.at(-1);
      const feedback = incoming?.to_node_id === node.id && incoming.outcome === 'feedback' ? incoming.data?.note : undefined;
      return <ImplementationStep {...step} plan={plan} feedback={node.data?.feedback ?? (typeof feedback === 'string' ? feedback : undefined)} />;
    }
    default:
      return <StepPane title={nodeLabel(node)} followLatest>
        <Conversation node={node} links={links} />
      </StepPane>;
  }
}
