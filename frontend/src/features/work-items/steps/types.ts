import type { WorkItemCommand, WorkNode } from '../types';

export interface StepProps {
  node: WorkNode;
  done: boolean;
  busy: boolean;
  perform: (command: WorkItemCommand) => void;
}
