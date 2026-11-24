import { useState } from 'react';
import { ImplementationChanges } from '../ImplementationChanges';
import { nodeLabel } from '../labels';
import { MessageMarkdown } from '../MessageMarkdown';
import type { ReviewDecision, WorkNode } from '../types';
import type { StepProps } from './types';
import { useNodeDraft } from './useNodeDraft';

const implementationChoices: { value: ReviewDecision; label: string }[] = [
  { value: 'accept', label: 'Accept this piece' },
  { value: 'feedback', label: 'Send feedback to the same worker' },
  { value: 'revise', label: 'Reopen implementation and retry' },
  { value: 'review_earlier', label: 'Review an earlier step' },
];

const earlierChoices: typeof implementationChoices = [
  { value: 'revise', label: 'Revise this step' },
  { value: 'return', label: 'Return to implementation review' },
];

interface Props extends StepProps {
  target: WorkNode;
  earlier: { id: number; label: string }[];
}

export function ReviewStep({ target, node, done, busy, links, perform, earlier }: Props) {
  const [{ text: note, reviewDecision }, saveDraft] = useNodeDraft(node.id);
  const choices = target.node_type === 'implementation'
    ? implementationChoices.filter(choice => choice.value !== 'review_earlier' || earlier.length > 0)
    : earlierChoices;
  const [decision, setDecision] = useState<ReviewDecision | ''>(() => choices.find(choice => choice.value === reviewDecision)?.value ?? '');
  const [earlierId, setEarlierId] = useState(earlier[0]?.id ?? null);
  const needsNote = decision === 'feedback' || decision === 'revise';
  const isImplementation = target.node_type === 'implementation';
  const summary = target.data?.summary || target.data?.approved;
  const commit = node.data?.last_decision?.reviewed_commit_sha || target.commit_sha;

  const actions = !done && !busy && <form className="review-form" onSubmit={event => {
    event.preventDefault();
    if (decision) {
      perform(
        { type: 'review', decision, note, earlier_id: decision === 'review_earlier' ? earlierId : null },
        () => saveDraft({ text: '' }),
      );
    }
  }}>
    <label>Decision
      <select value={decision} onChange={event => {
        const value = event.target.value;
        setDecision(choices.find(choice => choice.value === value)?.value ?? '');
      }} required>
        <option value="">Choose a decision</option>
        {choices.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>
    {needsNote && <label>What should change?
      <textarea value={note} onChange={event => saveDraft({ text: event.target.value, reviewDecision: decision })} rows={3} required />
    </label>}
    {decision === 'review_earlier' && <label>Earlier step
      <select value={earlierId ?? ''} onChange={event => setEarlierId(Number(event.target.value))} required>
        {earlier.map(({ id, label }) => <option key={id} value={id}>{label}</option>)}
      </select>
    </label>}
    <div><button className="primary" disabled={!decision || (needsNote && !note.trim())}>
      Record decision
    </button></div>
  </form>;

  const implementationDetails = <>
    {target.branch_ref && <p className="muted">Branch <code>{target.branch_ref.replace(/^refs\/heads\//, '')}</code></p>}
    {summary && <details className="step-disclosure">
      <summary>Implementation summary</summary>
      <MessageMarkdown text={summary} links={links} nodeId={target.id} />
    </details>}
    {actions}
  </>;

  const title = `Review ${nodeLabel(target).toLowerCase()}`;
  return <section className="step-pane" aria-label={title}>
    <div className="step-scroll" tabIndex={0} role="region" aria-label="Review content">
      <div className="step-content">
        {isImplementation ? (commit
          ? <ImplementationChanges key={commit} itemId={links.itemId} nodeId={node.id}>
            {implementationDetails}
          </ImplementationChanges>
          : <>
            <p className="muted">This implementation has no saved commit to compare.</p>
            {implementationDetails}
          </>) : <>
            <h3>{title}</h3>
            {summary && <MessageMarkdown text={summary} links={links} nodeId={target.id} />}
            {actions}
          </>}
      </div>
    </div>
  </section>;
}
