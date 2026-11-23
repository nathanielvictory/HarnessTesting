import { useEffect, useState } from 'react';
import { errorMessage } from '../api/request';
import { listProjects, registerProject } from '../features/projects/api';
import type { NewProject, Project } from '../features/projects/api';
import { createWorkItem, getWorkItem, listWorkItems, performWorkItemCommand } from '../features/work-items/api';
import type { WorkItem, WorkItemCommand, WorkItemDetail, WorkItemStatus } from '../features/work-items/types';

export function useWorkspace() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [filter, setFilter] = useState<WorkItemStatus>('in_progress');
  const [items, setItems] = useState<WorkItem[]>([]);
  const [listRevision, setListRevision] = useState(0);
  const [detail, setDetail] = useState<WorkItemDetail | null>(null);
  const [busy, setBusy] = useState('Loading projects…');
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

  function perform(command: WorkItemCommand) {
    if (!detail) return;
    const id = detail.work_item.id;
    return run('Working…', async () => {
      let updated = await performWorkItemCommand(id, command);
      setDetail(updated);
      if (command.type === 'approve' || command.type === 'review') {
        const next = followUpCommand(updated);
        if (next) {
          updated = await performWorkItemCommand(id, next);
          setDetail(updated);
        }
      }
      if (updated.work_item.status === 'complete') {
        setListRevision(revision => revision + 1);
      }
    });
  }

  return {
    projects, project: projects.find(project => project.id === projectId), projectId,
    filter, items, detail, busy, error, form,
    selectProject, selectFilter, toggleForm, register, createItem, openItem, perform,
  };
}

// Preserve the existing automatic follow-up after a browser approval or review.
function followUpCommand(detail: WorkItemDetail): WorkItemCommand | undefined {
  const current = detail.nodes.find(node => node.id === detail.current_node_id);
  if (current?.action === 'implementation') return { type: 'implement' };
  if (current?.action === 'technical_planning' && !current.messages.length) {
    return { type: 'messages', message: current.data?.revision_note || 'Draft the technical plan.' };
  }
}
