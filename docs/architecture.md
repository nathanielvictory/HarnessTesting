# Harness architecture

This document describes the current implementation. See the [product description](product.md) for intended behavior and the [glossary](glossary.md) for shared terms.

## Entry points and application boundaries

- The **browser** uses React and TypeScript. It calls the FastAPI endpoints through the Vite proxy. The frontend owns project and work item selection, conversation display, and review controls. The backend returns the graph, the ordered ready list, and blocker reasons.
- While a browser request runs an agent turn, the browser polls for recent tool calls and shows them beside the conversation. Activity is held in memory for the active request. Repository links in agent Markdown open files from the step's saved Git snapshot.
- **FastAPI and MCP** call the same [application service](../backend/src/harness/application.py) for catalog and work item operations. MCP exposes those operations over Streamable HTTP. The service permits one mutation per work item at a time within a server process.
- The **CLI** runs an interactive session and shares the catalog, graph repository, and work item operations with the server. It has its own terminal interaction and agent cancellation handling.
- [WorkSession](../backend/src/harness/operations/work_session.py) coordinates the operations for one work item. It coordinates scoped discovery, review, revision, and Git integration. The [traverser](../backend/src/harness/graph/traverser.py) defaults to the newest ready node, validates explicit selections, and persists each outcome.

## Graph and persistence

A project identifies a registered repository and groups work items. Creating a work item creates its goal alignment entry node. The graph repository loads the item's nodes and edges into an in-memory graph. Readiness comes from pending step state and prerequisites, not the transition log. Execution prerequisites refer to steps; acceptance prerequisites refer to stable scopes anchored at their original brief. Transition edges record what happened, including interrupted and replaced attempts. Legacy linear graphs recover their lifecycle from recorded transitions.

SQLAlchemy maps projects, work items, nodes, and edges to SQLite. The graph repository maps those records to the graph's Python objects and saves node state and transitions together. Agent-driven nodes can save their model, conversation, and node-specific data. Nodes can also save a branch ref and commit SHA. The API and MCP expose visible messages and graph history from this state.

The shared agent runner records Pydantic AI Harness `SpendLimits` events in SQLite as model responses arrive. Each record belongs to a graph node. The browser shows totals for the selected work item and project, including tokens and an estimated cost at API rates. For Codex subscription runs, that estimate describes equivalent API usage. Recording starts with new agent turns and runs without a spend ceiling.

## Path implemented today

The straight-line flow is brief → plan → implementation → review. At plan approval, the developer can instead delegate implementation to scoped pieces, each with its own path. Batch prerequisites name the pieces that need to be accepted before another can start. New nodes, prerequisites, and history are persisted in one transaction; dependency cycles roll back the batch.

Any ready step can add scoped prerequisites and wait for their acceptance. Implementation can also report missing prerequisites; Harness commits its edits and saves its conversation before opening the new briefs. The continuation starts on a separate branch with the saved edits and accepted prerequisite commits. The original attempt remains available in history. Reopening a brief, plan, or implementation replaces that step, invalidates dependent results, and leaves independent accepted work intact.

Accepting a review accepts its piece. Normal completion requires acceptance across the entire graph and a successful Git integration. The result is available at `refs/harness/results/<item-id>`; the developer’s original checkout is unchanged. An integration conflict keeps the review actionable and does not complete the item. The browser and MCP still offer explicit closure without acceptance or an integrated result.

## Agent context and Git

The [agent harness](../backend/src/harness/agents/harness.py) adapts Pydantic AI and restores the node's saved conversation for a new turn. Each operation supplies its own agent profile and builds the prompt for the turn.

- **Goal alignment** can list, search, and read repository files in the work item checkout at the Git baseline.
- **Technical planning** receives the approved brief and uses the same read-only tools against the baseline plus accepted prerequisites.
- **Implementation** receives the approved brief and plan, plus review feedback when applicable. It can read and edit files in the same checkout. Harness creates any resulting commit and records the branch ref and SHA.

Each work item uses a fixed checkout under `worktrees/items/` in the state directory and switches branches between steps. Harness reuses the checkout across turns and restarts, and recreates a missing checkout from the saved commit. On resumption, Harness checks that the branch still points to the saved SHA. Review decisions record the exact commit reviewed. Snapshot integration runs in a temporary detached worktree so a conflicting merge cannot change the saved step branches.

Run the Git-backed frontier regression suite with `cd backend && uv run python -m unittest -v test_frontier`.
