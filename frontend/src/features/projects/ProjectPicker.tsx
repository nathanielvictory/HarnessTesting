import type { FormEvent } from 'react';
import type { NewProject, Project } from './api';

interface Props {
  projects: Project[];
  projectId: number | null;
  busy: boolean;
  showForm: boolean;
  selectProject: (id: number) => void;
  toggleForm: () => void;
  register: (project: NewProject) => void;
}

export function ProjectPicker({ projects, projectId, busy, showForm, selectProject, toggleForm, register }: Props) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    register({
      name: String(fields.get('name') ?? ''),
      repository_path: String(fields.get('repository_path') ?? ''),
    });
  }

  return <section>
    <h2><label htmlFor="project">Project</label></h2>
    <select id="project" disabled={busy || !projects.length} value={projectId ?? ''}
      onChange={event => selectProject(Number(event.target.value))}>
      {!projects.length && <option value="">No projects</option>}
      {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
    </select>
    <button className="quiet" disabled={busy} onClick={toggleForm}>Register project</button>
    {showForm && <form className="stack" onSubmit={submit}>
      <label>Name<input name="name" required /></label>
      <label>Absolute repository path<input name="repository_path" required /></label>
      <button className="primary" disabled={busy}>Register</button>
    </form>}
  </section>;
}
