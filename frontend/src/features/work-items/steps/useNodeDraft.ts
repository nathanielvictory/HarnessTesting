import { useState } from 'react';

const prefix = 'harness:node-draft:';
const maxDrafts = 50;
const maxStoredCharacters = 256 * 1024;

interface Draft {
  text: string;
  reviewDecision?: string;
}

function readDraft(key: string): Draft {
  try {
    const value = localStorage.getItem(key) ?? 'null';
    const saved = JSON.parse(value.slice(value.indexOf('\n') + 1));
    if (typeof saved?.text === 'string') {
      return { text: saved.text, reviewDecision: typeof saved.reviewDecision === 'string' ? saved.reviewDecision : undefined };
    }
  } catch {
    // Draft storage can be unavailable or contain invalid data.
  }
  return { text: '' };
}

function saveDraft(key: string, draft: Draft) {
  try {
    if (!draft.text) {
      localStorage.removeItem(key);
      return;
    }

    // The timestamp prefix lets us evict older drafts without parsing their text.
    const value = `${Date.now()}\n${JSON.stringify(draft)}`;
    let size = key.length + value.length;
    if (size > maxStoredCharacters) return;

    const olderDrafts = Object.keys(localStorage).filter(name => name.startsWith(prefix) && name !== key)
      .map(name => {
        const value = localStorage.getItem(name) ?? '';
        return { name, size: name.length + value.length, updated: Number(value.split('\n', 1)[0]) || 0 };
      });
    for (const entry of olderDrafts) size += entry.size;
    olderDrafts.sort((a, b) => a.updated - b.updated);
    let count = olderDrafts.length + 1;
    for (const entry of olderDrafts) {
      if (count <= maxDrafts && size <= maxStoredCharacters) break;
      localStorage.removeItem(entry.name);
      size -= entry.size;
      count--;
    }
    localStorage.setItem(key, value);
  } catch {
    // Keep the form usable when the browser blocks storage or runs out of space.
  }
}

export function useNodeDraft(nodeId: number) {
  const key = `${prefix}${nodeId}`;
  const [draft, setDraft] = useState(() => readDraft(key));

  function update(next: Draft) {
    setDraft(next);
    saveDraft(key, next);
  }

  return [draft, update] as const;
}
