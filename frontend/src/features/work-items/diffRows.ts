import type { FileDiff } from './types';

export interface DiffLine {
  number: number;
  text: string;
  noNewline?: boolean;
}

interface DiffRow {
  before?: DiffLine;
  after?: DiffLine;
  changed: boolean;
}

interface DiffHunk {
  label: string;
  rows: DiffRow[];
}

function pairChanges(before: DiffLine[], after: DiffLine[]): DiffRow[] {
  return Array.from({ length: Math.max(before.length, after.length) }, (_, index) => ({
    before: before[index], after: after[index], changed: true,
  }));
}

function fileLines(text: string | undefined): DiffLine[] {
  if (!text) return [];
  const lines = text.split('\n');
  const endsWithNewline = lines.at(-1) === '';
  if (endsWithNewline) lines.pop();
  return lines.map((line, index) => ({
    number: index + 1,
    text: line,
    noNewline: !endsWithNewline && index === lines.length - 1,
  }));
}

export function diffHunks(diff: FileDiff): DiffHunk[] {
  if (diff.patch === undefined) {
    const rows = pairChanges(fileLines(diff.before), fileLines(diff.after));
    return rows.length ? [{ label: '', rows }] : [];
  }

  const hunks: DiffHunk[] = [];
  let hunk: DiffHunk | undefined;
  let oldNumber = 0;
  let newNumber = 0;
  let removed: DiffLine[] = [];
  let added: DiffLine[] = [];
  let previous: DiffLine[] = [];

  function flushChanges() {
    for (const row of pairChanges(removed, added)) hunk?.rows.push(row);
    removed = [];
    added = [];
  }

  for (const line of diff.patch.split('\n')) {
    const header = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
    if (header) {
      flushChanges();
      oldNumber = Number(header[1]);
      newNumber = Number(header[2]);
      hunk = { label: line, rows: [] };
      hunks.push(hunk);
      previous = [];
    } else if (hunk) {
      const text = line.slice(1);
      switch (line[0]) {
        case '-': {
          const before = { number: oldNumber++, text };
          removed.push(before);
          previous = [before];
          break;
        }
        case '+': {
          const after = { number: newNumber++, text };
          added.push(after);
          previous = [after];
          break;
        }
        case ' ': {
          flushChanges();
          const before = { number: oldNumber++, text };
          const after = { number: newNumber++, text };
          hunk.rows.push({ before, after, changed: false });
          previous = [before, after];
          break;
        }
        case '\\':
          for (const previousLine of previous) previousLine.noNewline = true;
          break;
      }
    }
  }
  flushChanges();
  return hunks;
}
