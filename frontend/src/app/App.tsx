import { ProjectPicker } from '../features/projects/ProjectPicker';
import { WorkItemList } from '../features/work-items/WorkItemList';
import { WorkItemScreen } from '../features/work-items/WorkItemScreen';
import { useWorkspace } from './useWorkspace';
import './layout.css';

export function App() {
  const state = useWorkspace();
  const busy = Boolean(state.busy);

  return (
    <div className="shell">
      <header className="topbar">
        <h1>Harness</h1>
        {state.project && <span className="repository" title={state.project.repository_path}>
          {state.project.repository_path}
        </span>}
      </header>
      <div className="layout">
        <aside className="navigator" aria-label="Projects and work items">
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
            openItem={state.openItem}
            toggleForm={() => state.toggleForm('item')}
            createItem={state.createItem}
          />}
        </aside>
        <main className="main">
          {state.error && <p className="notice error" role="alert">{state.error}</p>}
          {state.busy && !state.activity && <p className="notice" role="status">{state.busy}</p>}
          {state.detail
            ? <WorkItemScreen key={state.detail.work_item.id} detail={state.detail} busy={busy} activity={state.activity} perform={state.perform} />
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
