import type { RepositoryLinks } from '../MessageMarkdown';
import type { WorkItemActivity, WorkItemCommand, WorkNode } from '../types';

export interface StepProps {
  node: WorkNode;
  done: boolean;
  busy: boolean;
  activity: WorkItemActivity | null;
  links: RepositoryLinks;
  perform: (command: WorkItemCommand) => void;
}
