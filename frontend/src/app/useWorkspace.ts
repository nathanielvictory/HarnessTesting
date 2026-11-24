import { useEffect, useState } from 'react';
import { errorMessage } from '../api/request';
import { listProjects, registerProject } from '../features/projects/api';
import type { NewProject, Project } from '../features/projects/api';
import { createWorkItem, getWorkItem, getWorkItemActivity, listWorkItems, performWorkItemCommand } from '../features/work-items/api';
import type { WorkItem, WorkItemActivity, WorkItemCommand, WorkItemDetail, WorkItemStatus } from '../features/work-items/types';

export function useWorkspace() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [filter, setFilter] = useState<WorkItemStatus>('in_progress');
  const [items, setItems] = useState<WorkItem[]>([]);
  const [listRevision, setListRevision] = useState(0);
  const [detail, setDetail] = useState<WorkItemDetail | null>(null);
  const [busy, setBusy] = useState('Loading projects…');
  const [pending, setPending] = useState<{ id: number; label: string } | null>(null);
  const [toolCalls, setToolCalls] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [form, setForm] = useState<'project' | 'item' | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    listProjects(signal).then(rows => {
      if (signal.aborted) return;
      setProjects(rows);
      setProjectId(rows[0]?.id ?? null);
      if (!rows.length) setForm('project');
    }).catch(error => {
      if (!signal.aborted) setError(errorMessage(error));
    }).finally(() => {
      if (!signal.aborted) setBusy('');
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (projectId === null) return;
    const controller = new AbortController();
    const { signal } = controller;
    listWorkItems(projectId, filter, signal).then(rows => {
      if (!signal.aborted) setItems(rows);
    }).catch(error => {
      if (!signal.aborted) setError(errorMessage(error));
    });
    return () => controller.abort();
  }, [projectId, filter, listRevision]);

  useEffect(() => {
    if (!pending) return;
    const controller = new AbortController();
    const { signal } = controller;
    let timer: number | undefined;

    async function poll(id: number) {
      try {
        const current = await getWorkItemActivity(id, signal);
        if (!signal.aborted && current) setToolCalls(current.tools);
      } catch {
        // The work item request reports operation errors independently.
      } finally {
        if (!signal.aborted) timer = window.setTimeout(() => void poll(id), 350);
      }
    }

    void poll(pending.id);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [pending]);

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label);
    setError('');
    try {
      await action();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy('');
    }
  }

  function selectProject(id: number) {
    if (id === projectId) return;
    setProjectId(id);
    setItems([]);
    setDetail(null);
    setFilter('in_progress');
    setForm(null);
  }

  function selectFilter(status: WorkItemStatus) {
    if (status === filter) return;
    setItems([]);
    setFilter(status);
  }

  function toggleForm(target: 'project' | 'item') {
    setForm(current => current === target ? null : target);
  }

  function register(project: NewProject) {
    return run('Registering project', async () => {
      const registered = await registerProject(project);
      setProjects(rows => [...rows, registered]);
      selectProject(registered.id);
    });
  }

  function createItem(title: string) {
    if (projectId === null) return;
    return run('Creating work item', async () => {
      const item = await createWorkItem(projectId, title);
      selectFilter('in_progress');
      setListRevision(revision => revision + 1);
      setForm(null);
      setDetail(await getWorkItem(item.id));
    });
  }

  function openItem(id: number) {
    return run('Opening work item', async () => setDetail(await getWorkItem(id)));
  }

  function perform(command: WorkItemCommand, onSubmitted?: () => void) {
    if (!detail) return;
    const id = detail.work_item.id;
    function execute(step: WorkItemCommand, current: WorkItemDetail) {
      setToolCalls([]);
      setPending({ id, label: commandLabel(step, current) });
      return performWorkItemCommand(id, step);
    }
    const initial = detail;
    return run(commandLabel(command, initial), async () => {
      try {
        let updated = await execute(command, initial);
        onSubmitted?.();
        setDetail(updated);
        if (command.type === 'approve' || command.type === 'review') {
          const next = followUpCommand(updated);
          if (next) {
            updated = await execute(next, updated);
            setDetail(updated);
          }
        }
        if (updated.work_item.status === 'complete') {
          if (command.type === 'close') selectFilter('complete');
          setListRevision(revision => revision + 1);
        }
      } finally {
        setPending(null);
      }
    });
  }

  const activity: WorkItemActivity | null = pending ? { label: pending.label, tools: toolCalls } : null;
  return {
    projects, project: projects.find(project => project.id === projectId), projectId,
    filter, items, detail, busy, error, form, activity,
    selectProject, selectFilter, toggleForm, register, createItem, openItem, perform,
  };
}

function commandLabel(command: WorkItemCommand, detail: WorkItemDetail) {
  switch (command.type) {
    case 'messages':
      return detail.nodes.find(node => node.id === detail.current_node_id)?.node_type === 'technical_planning'
        ? 'Preparing the technical plan' : 'Preparing an alignment reply';
    case 'approve': return 'Saving approval';
    case 'implement': return 'Implementing the plan';
    case 'review': return 'Recording the review';
    case 'close': return 'Completing the work item';
  }
}

// Preserve the existing automatic follow-up after a browser approval or review.
function followUpCommand(detail: WorkItemDetail): WorkItemCommand | undefined {
  const current = detail.nodes.find(node => node.id === detail.current_node_id);
  if (current?.node_type === 'implementation') return { type: 'implement' };
  if (current?.node_type === 'technical_planning' && !current.messages.length) {
    return { type: 'messages', message: current.data?.revision_note || 'Draft the technical plan.' };
  }
}
