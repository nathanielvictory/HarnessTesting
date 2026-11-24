import { useState } from 'react';
import { Activity } from '../Activity';
import { nodeLabel } from '../labels';
import { MessageMarkdown } from '../MessageMarkdown';
import type { ReviewDecision, WorkNode } from '../types';
import type { StepProps } from './types';
import { useNodeDraft } from './useNodeDraft';

const implementationChoices: { value: ReviewDecision; label: string }[] = [
  { value: 'accept', label: 'Accept and complete' },
  { value: 'feedback', label: 'Send feedback to the same worker' },
  { value: 'revise', label: 'Revise the plan and retry' },
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

export function ReviewStep({ target, node, done, busy, activity, links, perform, earlier }: Props) {
  const [{ text: note, reviewDecision }, saveDraft] = useNodeDraft(node.id);
  const choices = target.node_type === 'implementation'
    ? implementationChoices.filter(choice => choice.value !== 'review_earlier' || earlier.length > 0)
    : earlierChoices;
  const [decision, setDecision] = useState<ReviewDecision | ''>(() => choices.find(choice => choice.value === reviewDecision)?.value ?? '');
  const [earlierId, setEarlierId] = useState(earlier[0]?.id ?? null);
  const needsNote = decision === 'feedback' || decision === 'revise';
  const summary = target.data?.summary || target.data?.approved;

  return <>
    <h3>Review {nodeLabel(target).toLowerCase()}</h3>
    <p className="step-description">
      {target.node_type === 'implementation'
        ? 'Check the saved changes against the brief. Accept when they meet the goal, send feedback for another implementation turn, or revisit the brief or plan if the direction needs to change.'
        : 'Read the decision that guided implementation. Revise it to try again from the original snapshot, or return to the implementation review.'}
    </p>
    {target.node_type === 'implementation' && target.branch_ref && <dl className="revision">
      <div><dt>Branch</dt><dd><code>{target.branch_ref.replace(/^refs\/heads\//, '')}</code></dd></div>
      <div><dt>Commit</dt><dd><code>{node.data?.last_decision?.reviewed_commit_sha || target.commit_sha}</code></dd></div>
    </dl>}
    {summary && <MessageMarkdown text={summary} links={links} nodeId={target.id} />}
    <Activity activity={activity} />
    {!done && !activity && <form className="stack" onSubmit={event => {
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
      <div><button className="primary" disabled={busy || !decision || (needsNote && !note.trim())}>
        Record decision
      </button></div>
    </form>}
  </>;
}
