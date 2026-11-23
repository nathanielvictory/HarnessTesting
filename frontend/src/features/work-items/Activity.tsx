import type { WorkItemActivity } from './types';

const toolLabels: Record<string, string> = {
  list_files: 'Requested a file listing',
  grep: 'Started a repository search',
  read_file: 'Requested a file read',
  edit_file: 'Requested a file edit',
  write_file: 'Requested a file write',
};

export function Activity({ activity }: { activity: WorkItemActivity | null }) {
  return <div role="status" aria-live="polite" className={activity ? 'activity' : undefined}>
    {activity && <>
      <p><span className="spinner" aria-hidden="true" />{activity.label}…</p>
      {activity.tools.length > 0 && <ul aria-label="Recent tool calls">
        {activity.tools.map((tool, index) => <li key={index}>{toolLabels[tool] ?? tool.replaceAll('_', ' ')}</li>)}
      </ul>}
    </>}
  </div>;
}
