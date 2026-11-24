# Harness

Local harness for LLM-assisted software development.

## Project documentation

- [Product](docs/product.md) describes the intended experience and dogfooding scenarios.
- [Glossary](docs/glossary.md) defines the terms used across the product and code.
- [Architecture](docs/architecture.md) describes the current implementation.
- [Development](docs/development.md) covers repository organization and verification.

## Run locally

From the repository root, start the Python backend in PowerShell. uv uses
Python 3.14 and creates `backend/.venv`.

```powershell
cd backend
uv sync --locked
uv run --locked harness-api
```

In a second terminal from the repository root, start the React frontend.

```powershell
cd frontend
npm ci
npm run dev
```

Open [Harness](http://127.0.0.1:5173). The frontend proxies `/api` to the
[FastAPI backend](http://127.0.0.1:8000/docs). In PyCharm, select
`backend\.venv\Scripts\python.exe` as the project interpreter.

Sign in with `codex login` before running an agent turn. The default model is
`openai-codex:gpt-6.2-sol` at medium reasoning effort. Set `HARNESS_MODEL` to
select another model. State defaults to `Harness` in local application data.
The runtime can also find an existing `HarnessTest` database. Set
`HARNESS_STATE_DIR` to choose a different location.

## Run with Docker Compose

Sign in once on the host with `codex login`, then run the development stack
from the repository root on Linux or Windows.

```powershell
docker compose -f infra/compose.yaml up --build
```

The browser, API docs, and MCP endpoint use the same local URLs as the native
setup. Set `HARNESS_FRONTEND_PORT` or `HARNESS_API_PORT` to run both setups at
once. Compose mounts `backend/` and `frontend/` for hot reload and keeps
container dependencies in their own volumes. The `harness-data` volume stores
`/data/harness.sqlite3` and persists across normal stops and restarts. Register
this repository as `/workspace/harness` inside the container.

Compose mounts the host's `.codex/auth.json` read-only for the Codex
subscription. It uses `CODEX_HOME` when set. Set `HARNESS_CODEX_AUTH_FILE`
if you need to point Compose to a specific login file.

## Connect Codex over MCP

Keep the backend running and register its local Streamable HTTP endpoint.

```powershell
codex mcp add harness --url http://127.0.0.1:8000/mcp
```

The MCP tools inspect and act on the same projects and work items as the web app.
Use `inspect_work_item` to find the ready node's ID and whether it has a saved
conversation. Pass the node ID to `start_node` for its first turn or to
`send_message` for a follow-up. Approval, discovery, and review also require a
node ID.

## Inspect a work item checkout

To inspect the implementation branch in your IDE, open the work item's existing
checkout under `worktrees/items/<work-item-id>` in the Harness state directory.
