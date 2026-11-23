import { request } from '../../api/request';

export interface Project {
  id: number;
  name: string;
  repository_path: string;
}

export type NewProject = Pick<Project, 'name' | 'repository_path'>;

export function listProjects(signal: AbortSignal) {
  return request<Project[]>('/projects', undefined, signal);
}

export function registerProject(project: NewProject) {
  return request<Project>('/projects', project);
}
