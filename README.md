# HarnessTest

Local workflow harness for LLM-assisted software development.

## Development setup

Install uv, then run these commands from the checkout in PowerShell. uv uses
Python 3.14 and creates a `.venv` in the checkout.

```powershell
uv sync --locked
uv run --locked harness --help
```

In PyCharm, select `.venv\Scripts\python.exe` as the project interpreter.

The CLI entry point lives in `src/harness_test/cli/__init__.py`.

## Run the harness

Sign in with `codex login`, then run `uv run --locked harness`. Register a Git
repository by its absolute path and open a work item. The default agent model is
`openai-codex:gpt-6.2-sol` at medium reasoning effort. Set `HARNESS_MODEL` to
select another model.

During alignment and planning, use `/approve` to accept the displayed draft.
`/graph` shows the saved graph and `/quit` closes the harness. During an agent
turn in a terminal, press `G` to view the graph or `Q` to save and quit.

Review shows the implementation branch and commit. Accepting completes the
work item and leaves its branch available for integration. Feedback resumes
the same worker conversation. Revising the plan starts a fresh implementation
branch from the plan's base commit. Earlier-step review lets you revisit an
approved plan or brief.

State defaults to `HarnessTest` under the local application-data directory.
Set `HARNESS_STATE_DIR` to use another location. If you check out an implementation
branch in your IDE, switch away from it before asking the harness to edit it again.
