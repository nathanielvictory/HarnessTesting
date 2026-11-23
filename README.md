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

The CLI lives in `src/harness_test/cli.py`. The environment includes Pydantic AI
Harness and its OpenAI provider for future worker nodes.
