import { useState } from 'react';
import { ProjectPicker } from '../features/projects/ProjectPicker';
import { UsageSummary } from '../features/usage/UsageSummary';
import { workItemTitle } from '../features/work-items/labels';
import { WorkItemList } from '../features/work-items/WorkItemList';
import { WorkItemScreen } from '../features/work-items/WorkItemScreen';
import { useWorkspace } from './useWorkspace';
import './layout.css';

export function App() {
  const state = useWorkspace();
  const [navigatorOpen, setNavigatorOpen] = useState(false);
  const busy = Boolean(state.busy);
  const item = state.detail?.work_item;

  return (
    <div className="shell">
      <header className="topbar">
        <h1>Harness</h1>
        {item ? <h2 className="topbar-context" title={workItemTitle(item)}>{workItemTitle(item)}</h2> :
          state.project && <span className="topbar-context" title={state.project.repository_path}>{state.project.name}</span>}
        {item?.status === 'complete' && <span className="topbar-status">Complete</span>}
        <div className="topbar-actions">
          {item && <button className="navigator-toggle" aria-expanded={navigatorOpen} aria-controls="workspace-navigator"
            onClick={() => setNavigatorOpen(open => !open)}>Work items</button>}
          {state.project && <>
            <button popoverTarget="workspace-usage">Usage</button>
            <div className="toolbar-popover" id="workspace-usage" popover="auto">
              {item && <UsageSummary key={`item-${item.id}`} scope="work-items" id={item.id} busy={busy} />}
              <UsageSummary key={`project-${state.project.id}`} scope="projects" id={state.project.id} busy={busy} />
            </div>
          </>}
          {item?.status === 'in_progress' && <>
            <button popoverTarget="workspace-item-actions" aria-label="Work item actions">More</button>
            <div className="toolbar-popover" id="workspace-item-actions" popover="auto">
              <button disabled={busy} onClick={event => {
                event.currentTarget.closest<HTMLElement>('[popover]')?.hidePopover();
                state.perform({ type: 'close' });
              }}>Mark complete</button>
            </div>
          </>}
        </div>
      </header>
      <div className="layout" data-has-item={Boolean(item)}>
        <aside className="navigator" id="workspace-navigator" data-expanded={navigatorOpen} aria-label="Projects and work items">
          <ProjectPicker
            projects={state.projects}
            projectId={state.projectId}
            busy={busy}
            showForm={state.form === 'project'}
            selectProject={state.selectProject}
            toggleForm={() => state.toggleForm('project')}
            register={state.register}
          />
          {state.project && <WorkItemList
            items={state.items}
            filter={state.filter}
            selectedId={state.detail?.work_item.id}
            busy={busy}
            showForm={state.form === 'item'}
            selectFilter={state.selectFilter}
            openItem={id => {
              void state.openItem(id);
              setNavigatorOpen(false);
            }}
            toggleForm={() => state.toggleForm('item')}
            createItem={state.createItem}
          />}
        </aside>
        <main className="main">
          {state.error && <p className="notice error" role="alert">{state.error}</p>}
          {state.busy && <p className="notice" role="status">{state.busy}</p>}
          {state.detail
            ? <WorkItemScreen key={state.detail.work_item.id} detail={state.detail} busy={busy} perform={state.perform} />
            : <div className="empty">
              <h2>{state.project ? 'Open a work item' : 'Register a repository'}</h2>
              <p>{state.project
                ? 'Choose an existing item or create a new one to start goal alignment.'
                : 'Add the local Git repository you want the harness to work with.'}</p>
            </div>}
        </main>
      </div>
    </div>
  );
}
