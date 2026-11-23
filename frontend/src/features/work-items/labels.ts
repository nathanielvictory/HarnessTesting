import type { WorkItem, WorkNode } from './types';

const actionLabels: Readonly<Record<string, string>> = {
  goal_alignment: 'Goal alignment',
  technical_planning: 'Technical planning',
  implementation: 'Implementation',
  human_review: 'Human review',
  automated_review: 'Automated review',
  run_python: 'Run Python',
};

export function nodeLabel(node?: WorkNode): string {
  return node ? actionLabels[node.action] ?? node.action : 'No active step';
}

export function workItemTitle(item: WorkItem): string {
  return item.title || `Work item ${item.id}`;
}
