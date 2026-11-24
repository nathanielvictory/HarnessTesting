import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { errorMessage } from '../../api/request';
import { getFileDiff, getImplementationDiff } from './api';
import { diffHunks } from './diffRows';
import type { DiffLine } from './diffRows';
import type { ChangedFile, FileDiff, ImplementationDiff } from './types';
import './implementation-changes.css';

const changeLabels: Record<string, string> = {
  A: 'Added', D: 'Deleted', M: 'Modified', R: 'Renamed', C: 'Copied', T: 'Type changed',
};

function fileName(file: ChangedFile) {
  return file.new_path ?? file.old_path ?? '';
}

export function ImplementationChanges({ itemId, nodeId, children }: { itemId: number; nodeId: number; children?: ReactNode }) {
  const [diff, setDiff] = useState<ImplementationDiff | null>(null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<number | null>(null);
  const filesRef = useRef<HTMLUListElement>(null);
  const backRef = useRef<HTMLButtonElement>(null);
  const lastSelected = useRef<number | null>(null);

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

  useLayoutEffect(() => {
    if (selected !== null) {
      backRef.current?.focus({ preventScroll: true });
      backRef.current?.scrollIntoView({ block: 'start' });
    } else if (lastSelected.current !== null) {
      filesRef.current?.querySelectorAll('button')[lastSelected.current]?.focus();
    }
  }, [selected]);

  const file = selected === null ? undefined : diff?.files[selected];
  if (diff && selected !== null && file) {
    return <section className="step-section changes-panel" aria-label={`Comparison for ${fileName(file)}`}>
      <button type="button" className="back-to-files" ref={backRef} onClick={() => setSelected(null)}>← Back to files</button>
      <h4 className="compared-file"><code>{fileName(file)}</code></h4>
      <FileComparison key={`${diff.commit}:${selected}`} itemId={itemId} nodeId={nodeId} index={selected}
        commit={diff.commit} file={file} />
    </section>;
  }

  return <section className="step-section changes-panel" aria-label="Saved changes">
    <h4>Saved changes</h4>
    {error ? <p role="status">Changes unavailable. {error}</p> : !diff ? <p role="status">Loading changed files…</p> : <>
      <p className="muted changes-meta">{diff.files.length} {diff.files.length === 1 ? 'file' : 'files'} ·{' '}
        <code title={diff.base_commit}>{diff.base_commit.slice(0, 8)}</code> to{' '}
        <code title={diff.commit}>{diff.commit.slice(0, 8)}</code></p>
      {diff.files.length ?
        <ul className="changed-files" ref={filesRef} aria-label="Changed files">
          {diff.files.map((change, index) => <li key={index}>
            <button type="button" onClick={() => {
              lastSelected.current = index;
              setSelected(index);
            }}>
              <span className="file-status" data-status={change.status}>{changeLabels[change.status] ?? 'Changed'}</span>
              <span>{fileName(change)}</span>
            </button>
          </li>)}
        </ul> : <p>No file changes in this snapshot.</p>}
    </>}
    {children}
  </section>;
}

function FileComparison({ itemId, nodeId, index, commit, file }: {
  itemId: number; nodeId: number; index: number; commit: string; file: ChangedFile;
}) {
  const [diff, setDiff] = useState<FileDiff | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    getFileDiff(itemId, nodeId, index, commit, signal).then(result => {
      if (!signal.aborted) setDiff(result);
    }).catch(reason => {
      if (!signal.aborted) setError(errorMessage(reason));
    });
    return () => controller.abort();
  }, [itemId, nodeId, index, commit]);

  const hunks = diff && !diff.binary ? diffHunks(diff) : [];
  return <>
    {file.old_path && file.new_path && file.old_path !== file.new_path &&
      <p className="muted">Original path <code>{file.old_path}</code></p>}
    {file.old_path && file.new_path && file.old_mode !== file.new_mode &&
      <p className="muted">File mode {file.old_mode} → {file.new_mode}</p>}
    {error ? <p role="status">Comparison unavailable. {error}</p> : !diff ? <p role="status">Loading file comparison…</p> :
      diff.binary ? <p>Binary file. A line comparison is unavailable.</p> : hunks.length === 0 ? <p>No text lines changed.</p> :
        <table className="file-diff">
          <colgroup><col className="diff-number-column" /><col /></colgroup>
          <colgroup><col className="diff-number-column" /><col /></colgroup>
          <thead><tr>
            <th scope="colgroup" colSpan={2}>Original</th>
            <th scope="colgroup" colSpan={2}>Changed</th>
          </tr></thead>
          {hunks.map((hunk, index) => <tbody key={index}>
            {hunk.label && <tr className="diff-hunk"><td colSpan={4}>{hunk.label}</td></tr>}
            {hunk.rows.map((row, rowIndex) => <tr key={rowIndex}>
              <DiffCells line={row.before} marker={row.changed ? '−' : undefined} />
              <DiffCells line={row.after} marker={row.changed ? '+' : undefined} />
            </tr>)}
          </tbody>)}
        </table>}
  </>;
}

function DiffCells({ line, marker }: { line?: DiffLine; marker?: '−' | '+' }) {
  const color = !line ? 'diff-empty' : marker === '−' ? 'diff-removed' : marker === '+' ? 'diff-added' : undefined;
  return <>
    <td className={`diff-number ${color ?? ''}`}>{line?.number}</td>
    <td className={color}>{line && <>
      <span className="diff-marker" aria-hidden="true">{marker}</span>
      <code>{line.text}</code>
      {line.noNewline && <abbr className="diff-eol" title="No newline at end of file">∅</abbr>}
    </>}</td>
  </>;
}
