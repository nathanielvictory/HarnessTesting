# Developing Harness

Follow the [glossary](glossary.md) in code, prompts, UI labels, and docs. When a term changes, review those uses together. Use the [product description](product.md) for intended behavior and the [architecture](architecture.md) to locate the implementation.

## Repository organization

| Location | Responsibility |
| --- | --- |
| `backend/src/harness/api/` | Adapt HTTP and MCP interactions to application operations. Keep interface-specific formatting and interaction here. |
| `backend/src/harness/graph/` | Represent the graph, reconstruct its history, and traverse it. |
| `backend/src/harness/operations/` | Define what nodes do, assemble their instructions and inputs, and coordinate transitions for a work item. |
| `backend/src/harness/persistence/` | Define SQLAlchemy models and map stored state to and from application objects. |
| `backend/src/harness/agents/` and `git/` | Adapt Pydantic AI and Git to the operations that use them. |
| `frontend/src/app/` | Compose the browser interface and manage workspace selection and loading. |
| `frontend/src/features/` | Keep project and work item UI, API calls, types, and feature-specific styles near the features that use them. Put new node views alongside the other views for that work item. |
| `frontend/src/api/` | Handle shared HTTP transport and errors. |
| `infra/` | Define the local Compose stack. |

## Coding practices

- Use Python 3.14 and uv in `backend/`. Use strict TypeScript for React and Vite in `frontend/`. Keep dependency changes in the appropriate lockfile.
- Organize substantial concerns in their own directories. Within a directory, split files by what they do. Use a class where it makes state or ownership easier to follow, such as a work session or repository.
- Keep traversal, node execution, and persistence decisions in their respective layers. Put instructions and tool access with the operation that needs them. Keep graph transition rules in backend application code so entry points can share them.
- Keep changes scoped to the agreed work item. When a change exposes a consequential decision about the brief or plan, use the work item's conversation to surface the finding and decide where to resume.

## Verification and review

Use the setup commands in the [README](../README.md).

- For frontend changes, run `npm run build` from `frontend/`. It checks types and builds the app. Exercise affected interactions through the browser when behavior changes.
- For backend changes, exercise the affected operation through its normal entry point. Use a disposable database or repository for checks that change saved state or create Git commits.
- For graph or Git changes, cover the relevant resume or rollback case as well as the forward path. Check that the saved conversation, graph history, and Git state remain usable where the change touches them.
- For Compose changes, validate the configuration with `docker compose -f infra/compose.yaml config`. Test startup or restart when the change affects service wiring or persistence.

Record the brief, discoveries, review feedback, and verification for active work in the work item. When accepted work changes something the next developer needs to know, update the corresponding repo doc with that change.
