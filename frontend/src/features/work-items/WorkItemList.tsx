import type { FormEvent } from 'react';
import type { WorkItem, WorkItemStatus } from './types';
import { workItemTitle } from './labels';
import './work-item-list.css';

const filters: { status: WorkItemStatus; label: string }[] = [
  { status: 'in_progress', label: 'In progress' },
  { status: 'complete', label: 'Complete' },
];

interface Props {
  items: WorkItem[];
  filter: WorkItemStatus;
  selectedId?: number;
  busy: boolean;
  showForm: boolean;
  selectFilter: (status: WorkItemStatus) => void;
  openItem: (id: number) => void;
  toggleForm: () => void;
  createItem: (title: string) => void;
}

export function WorkItemList({ items, filter, selectedId, busy, showForm, selectFilter, openItem, toggleForm, createItem }: Props) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createItem(String(new FormData(event.currentTarget).get('title') ?? ''));
  }

  return <section>
    <h2>Work items</h2>
    <div className="filters" aria-label="Work item status">
      {filters.map(({ status, label }) => (
        <button key={status} disabled={busy} aria-pressed={filter === status} onClick={() => selectFilter(status)}>
          {label}
        </button>
      ))}
    </div>
    <ul className="items">
      {items.map(item => <li key={item.id}>
        <button aria-current={item.id === selectedId ? 'true' : undefined} disabled={busy} onClick={() => openItem(item.id)}>
          {workItemTitle(item)}
        </button>
      </li>)}
    </ul>
    {!items.length && <p className="muted">No {filter === 'in_progress' ? 'in-progress' : 'completed'} items.</p>}
    <button className="quiet" disabled={busy} onClick={toggleForm}>New work item</button>
    {showForm && <form className="stack" onSubmit={submit}>
      <label>Title <span className="muted">(optional)</span><input name="title" /></label>
      <button className="primary" disabled={busy}>Create</button>
    </form>}
  </section>;
}
