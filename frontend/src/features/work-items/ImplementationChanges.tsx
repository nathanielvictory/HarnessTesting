import { useEffect, useState } from 'react';
import { errorMessage } from '../../api/request';
import { getImplementationDiff } from './api';
import type { ImplementationDiff } from './types';

export function ImplementationChanges({ itemId, nodeId }: { itemId: number; nodeId: number }) {
  const [diff, setDiff] = useState<ImplementationDiff | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    getImplementationDiff(itemId, nodeId, signal).then(result => {
      if (!signal.aborted) setDiff(result);
    }).catch(reason => {
      if (!signal.aborted) setError(errorMessage(reason));
    });
    return () => controller.abort();
  }, [itemId, nodeId]);

  return <section className="step-section" aria-label="Saved changes">
    <h4>Saved changes</h4>
    {error ? <p role="status">Diff unavailable. {error}</p> : !diff ? <p role="status">Loading diff…</p> : <>
      <p className="muted">Compared <code title={diff.base_commit}>{diff.base_commit.slice(0, 8)}</code> to{' '}
        <code title={diff.commit}>{diff.commit.slice(0, 8)}</code>.</p>
      {diff.patch ? <details className="step-disclosure">
        <summary>View Git diff</summary>
        {diff.truncated && <p className="muted">Preview truncated.{' '}
          <a href={`/api/work-items/${itemId}/nodes/${nodeId}/diff.patch`} target="_blank" rel="noopener noreferrer">
            Open full diff
          </a>
        </p>}
        <pre className="git-diff" role="region" aria-label="Git diff" tabIndex={0}><code>{diff.patch.split('\n').map((line, index) =>
          <span key={index} className={line.startsWith('+') ? 'diff-added' : line.startsWith('-') ? 'diff-removed' : undefined}>
            {line}{'\n'}
          </span>,
        )}</code></pre>
      </details> : <p>No file changes in this snapshot.</p>}
    </>}
  </section>;
}
