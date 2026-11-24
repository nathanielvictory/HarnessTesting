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
  conversation_started: boolean;
  status: 'pending' | 'done' | 'superseded';
  scope_id: number;
  scope_brief: string | null;
  data: {
    scope_brief?: string;
    draft?: string;
    approved?: string;
    summary?: string;
    base_commit?: string | null;
    plan_id?: number;
    target_id?: number;
    paused?: boolean;
    feedback?: string;
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
  ready_node_ids: number[];
  blocked: Record<number, { node_id: number; reason: string }[]>;
  result_commit: string | null;
  reviews: Record<number, Review>;
  nodes: WorkNode[];
  transitions: Transition[];
}

export type ReviewDecision = 'accept' | 'feedback' | 'revise' | 'review_earlier' | 'return';

export interface ImplementationDiff {
  base_commit: string;
  commit: string;
  files: ChangedFile[];
}

export interface ChangedFile {
  status: string;
  old_path: string | null;
  new_path: string | null;
  old_mode: string;
  new_mode: string;
}

export interface FileDiff {
  binary: boolean;
  patch?: string;
  before?: string;
  after?: string;
}

export interface ScopedWork {
  brief: string;
  depends_on: number[];
}

export type WorkItemCommand = { type: 'close' } | ({ node_id: number } & (
  | { type: 'start'; message?: string }
  | { type: 'messages'; message: string }
  | { type: 'approve'; pieces?: ScopedWork[] }
  | { type: 'discover'; pieces: ScopedWork[] }
  | { type: 'reopen'; note: string }
  | { type: 'review'; decision: ReviewDecision; note: string; earlier_id: number | null }
));
