import type { RepositoryLinks } from '../MessageMarkdown';
import type { WorkItemCommand, WorkNode } from '../types';

export type PerformCommand = (command: WorkItemCommand, onSubmitted?: () => void) => void;

export interface StepProps {
  node: WorkNode;
  done: boolean;
  busy: boolean;
  links: RepositoryLinks;
  perform: PerformCommand;
}
