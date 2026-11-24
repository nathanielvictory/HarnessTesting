import { request } from '../../api/request';
import type { FileDiff, ImplementationDiff, WorkItem, WorkItemCommand, WorkItemDetail, WorkItemStatus } from './types';

export function listWorkItems(projectId: number, status: WorkItemStatus, signal: AbortSignal) {
  return request<WorkItem[]>(`/projects/${projectId}/work-items?status=${status}`, undefined, signal);
}

export function createWorkItem(projectId: number, title: string) {
  return request<WorkItem>(`/projects/${projectId}/work-items`, { title });
}

export function getWorkItem(id: number) {
  return request<WorkItemDetail>(`/work-items/${id}`);
}

export function getImplementationDiff(itemId: number, nodeId: number, signal: AbortSignal) {
  return request<ImplementationDiff>(`/work-items/${itemId}/nodes/${nodeId}/diff`, undefined, signal);
}

export function getFileDiff(itemId: number, nodeId: number, fileIndex: number, commit: string, signal: AbortSignal) {
  return request<FileDiff>(`/work-items/${itemId}/nodes/${nodeId}/diff/files/${fileIndex}?commit=${encodeURIComponent(commit)}`,
    undefined, signal);
}

export function performWorkItemCommand(id: number, { type, ...body }: WorkItemCommand) {
  return request<WorkItemDetail>(`/work-items/${id}/${type}`, body);
}
