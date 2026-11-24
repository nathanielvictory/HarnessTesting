import { useState } from 'react';
import { UsageSummary } from '../usage/UsageSummary';
import { Activity } from './Activity';
import { Conversation } from './Conversation';
import { GraphHistory } from './GraphHistory';
import { nodeLabel, workItemTitle } from './labels';
import type { RepositoryLinks } from './MessageMarkdown';
import { DiscussionStep } from './steps/DiscussionStep';
import { ImplementationStep } from './steps/ImplementationStep';
import { ReviewStep } from './steps/ReviewStep';
import type { ScopedWork, WorkItemActivity, WorkItemCommand, WorkItemDetail, WorkNode } from './types';
import './work-item.css';

interface Props {
  detail: WorkItemDetail;
  busy: boolean;
  activity: WorkItemActivity | null;
  perform: (command: WorkItemCommand) => void;
}

export function WorkItemScreen({ detail, busy, activity, perform }: Props) {
  const [historyId, setHistoryId] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const currentId = selectedId !== null && detail.ready_node_ids.includes(selectedId)
    ? selectedId : detail.current_node_id;
  const current = detail.nodes.find(node => node.id === currentId);
  const historical = detail.nodes.find(node => node.id === historyId);
  const done = detail.work_item.status === 'complete';
  const links = { itemId: detail.work_item.id, repositoryPath: detail.project.repository_path };

  return <>
    <div className="item-heading">
      <div>
        <h2>{workItemTitle(detail.work_item)}</h2>
        <p className="muted">{done ? detail.result_commit ? 'Complete' : 'Closed / no integrated result recorded' : nodeLabel(current)}</p>
        {current?.scope_brief && <p>{current.scope_brief}</p>}
        {detail.result_commit && <code>{detail.result_commit}</code>}
      </div>
      {!done && <button disabled={busy} onClick={() => perform({ type: 'close' })}>Close without acceptance</button>}
    </div>
    {detail.ready_node_ids.length > 1 && <label>Ready step (newest first) <select disabled={busy}
      value={currentId ?? ''} onChange={event => { setSelectedId(Number(event.target.value)); setHistoryId(null); }}>
      {detail.ready_node_ids.map(id => <option key={id} value={id}>{stepLabel(detail, id)}</option>)}
    </select></label>}
    {!done && Object.keys(detail.blocked).length > 0 && <ul aria-label="Blocked steps">
      {Object.entries(detail.blocked).map(([id, blockers]) => <li key={id}>
        <button onClick={() => setHistoryId(Number(id))}>{stepLabel(detail, Number(id))}</button>
        {blockers.map(({ node_id, reason }) => <span key={`${node_id}:${reason}`}> · {reason}: {stepLabel(detail, node_id)}</span>)}
      </li>)}
    </ul>}
    <UsageSummary scope="work-items" id={detail.work_item.id} busy={busy} />
    <div className="work-grid">
      <section className="panel">
        {historical && historical.id !== current?.id
          ? <>
            <div className="panel-heading">
              <h3>{nodeLabel(historical)}</h3>
              <button onClick={() => setHistoryId(null)}>Back to current step</button>
            </div>
            {historical.commit_sha && <p>Snapshot <code>{historical.commit_sha}</code></p>}
            <Conversation node={historical} links={links} />
            {!done && <ReopenForm key={historical.id} node={historical} busy={busy} perform={perform} />}
            <Activity activity={activity} />
          </>
          : current ? <div key={current.id}>
            <CurrentStep node={current} detail={detail} busy={busy} activity={activity}
              perform={command => perform({ ...command, node_id: current.id })} links={links} />
            <ScopeForm node={current} busy={busy} perform={perform} />
            <ReopenForm node={current} busy={busy} perform={perform} />
          </div> : !done && <p>No steps are ready. Review the blockers and graph history.</p>}
      </section>
      <GraphHistory detail={detail} selectNode={setHistoryId} />
    </div>
  </>;
}

function stepLabel(detail: WorkItemDetail, id: number) {
  const node = detail.nodes.find(candidate => candidate.id === id);
  return `#${id} ${nodeLabel(node)}${node?.scope_brief ? ` · ${node.scope_brief}` : ''}`;
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
      perform(split ? { type: 'approve', node_id: node.id, pieces: batch }
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
        Approve this plan and delegate its implementation to these pieces
      </label>}
      {error && <p role="alert">{error}</p>}
      <button disabled={busy}>{split ? 'Approve and delegate' : 'Pause step and add prerequisites'}</button>
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
      <button disabled={busy || !note.trim()}>Reopen</button>
    </form>
  </details>;
}

function CurrentStep({ node, detail, busy, activity, perform, links }: Props & { links: RepositoryLinks; node: WorkNode }) {
  const done = detail.work_item.status === 'complete';
  const step = { node, done, busy, activity, perform, links };

  const review = detail.reviews[node.id];
  if (review) {
    const target = detail.nodes.find(candidate => candidate.id === review.target_id);
    if (!target) return <p role="alert">The step under review could not be found.</p>;
    const earlier = review.earlier_ids.map(id => ({
      id,
      label: nodeLabel(detail.nodes.find(candidate => candidate.id === id)),
    }));
    return <ReviewStep {...step} target={target} earlier={earlier} />;
  }
  switch (node.node_type) {
    case 'goal_alignment':
    case 'technical_planning':
      return <DiscussionStep {...step} alignment={node.node_type === 'goal_alignment'} />;
    case 'implementation':
      return <ImplementationStep {...step} />;
    default:
      return <>
        <h3>{nodeLabel(node)}</h3>
        <Conversation node={node} links={links} />
        <Activity activity={activity} />
      </>;
  }
}
