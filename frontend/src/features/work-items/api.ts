import { request } from '../../api/request';
import type { WorkItem, WorkItemActivity, WorkItemCommand, WorkItemDetail, WorkItemStatus } from './types';

export function listWorkItems(projectId: number, status: WorkItemStatus, signal: AbortSignal) {
  return request<WorkItem[]>(`/projects/${projectId}/work-items?status=${status}`, undefined, signal);
}

export function createWorkItem(projectId: number, title: string) {
  return request<WorkItem>(`/projects/${projectId}/work-items`, { title });
}

export function getWorkItem(id: number) {
  return request<WorkItemDetail>(`/work-items/${id}`);
}

export function getWorkItemActivity(id: number, signal: AbortSignal) {
  return request<WorkItemActivity | null>(`/work-items/${id}/activity`, undefined, signal);
}

export function performWorkItemCommand(id: number, { type, ...body }: WorkItemCommand) {
  return request<WorkItemDetail>(`/work-items/${id}/${type}`, body);
}
