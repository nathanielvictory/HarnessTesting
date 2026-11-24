import type { RepositoryLinks } from '../MessageMarkdown';
import type { WorkItemActivity, WorkItemCommand, WorkNode } from '../types';

export type PerformCommand = (command: WorkItemCommand, onSubmitted?: () => void) => void;

export interface StepProps {
  node: WorkNode;
  done: boolean;
  busy: boolean;
  activity: WorkItemActivity | null;
  links: RepositoryLinks;
  perform: PerformCommand;
}
