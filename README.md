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

From the repository root, run the development stack.

```powershell
docker compose -f infra/compose.yaml up --build
```

The browser, API docs, and MCP endpoint use the same local URLs as the native
setup. Set `HARNESS_FRONTEND_PORT` or `HARNESS_API_PORT` to run both setups at
once. Compose mounts `backend/` and `frontend/` for hot reload and keeps
container dependencies in their own volumes. The `harness-data` volume stores
`/data/harness.sqlite3` and persists across normal stops and restarts. Register
this repository as `/workspace/harness` inside the container.

To use the Codex subscription from Compose, include the optional read-only
credential mount. `HARNESS_CODEX_AUTH_FILE` should point to the `auth.json`
created by `codex login`.

```powershell
$env:HARNESS_CODEX_AUTH_FILE = Join-Path $env:USERPROFILE '.codex\auth.json'
docker compose -f infra/compose.yaml -f infra/compose.codex.yaml up --build
```

## Connect Codex over MCP

Keep the backend running and register its local Streamable HTTP endpoint.

```powershell
codex mcp add harness --url http://127.0.0.1:8000/mcp
```

The MCP tools inspect and act on the same projects and work items as the web app.

## Use the terminal interface

From `backend/`, run `uv run --locked harness`. During alignment and planning,
use `/approve` to accept the displayed draft. `/graph` shows the saved graph and
`/quit` closes the harness. During an agent turn, press `G` to view the graph or
`Q` to save and quit.

Review shows the implementation branch and commit. Accepting completes the
work item and leaves its branch available for integration. Feedback resumes
the same worker conversation. Revising the plan starts a fresh implementation
branch from the plan's base commit. Earlier-step review lets you revisit an
approved plan or brief.

If you check out an implementation branch in your IDE, switch away from it
before asking the harness to edit it again.
