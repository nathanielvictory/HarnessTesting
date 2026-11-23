import type { Project } from '../projects/api';

export type WorkItemStatus = 'in_progress' | 'complete';

export interface WorkItem {
  id: number;
  title: string | null;
  status: WorkItemStatus;
}

export interface WorkNode {
  id: number;
  node_type: string;
  model: string | null;
  branch_ref: string | null;
  commit_sha: string | null;
  data: {
    draft?: string;
    approved?: string;
    summary?: string;
    base_commit?: string | null;
    revision_note?: string;
    last_decision?: { reviewed_commit_sha?: string };
    [field: string]: unknown;
  } | null;
  messages: { role: 'user' | 'assistant'; text: string }[];
}

export interface Transition {
  from_node_id: number;
  to_node_id: number;
  outbound_order: number;
  outcome: string;
  data: { reviewed_commit_sha?: string; [field: string]: unknown } | null;
}

export interface Review {
  target_id: number;
  earlier_ids: number[];
  return_review_id: number | null;
}

export interface WorkItemDetail {
  project: Project;
  work_item: WorkItem;
  entry_node_id: number | null;
  current_node_id: number | null;
  nodes: WorkNode[];
  transitions: Transition[];
  review: Review | null;
}

export type ReviewDecision = 'accept' | 'feedback' | 'revise' | 'review_earlier' | 'return';

export type WorkItemCommand =
  | { type: 'messages'; message: string }
  | { type: 'approve'; base_ref?: string | null }
  | { type: 'implement' }
  | { type: 'review'; decision: ReviewDecision; note: string; earlier_id: number | null };
