# Harness architecture

This document describes the current implementation. See the [product description](product.md) for intended behavior and the [glossary](glossary.md) for shared terms.

## Entry points and application boundaries

- The browser uses React and TypeScript and calls FastAPI through the Vite proxy. The backend exposes the graph, conversations, ready nodes, blocker reasons, and per-file Git diffs.
- FastAPI and MCP use [Harness](../backend/src/harness/application.py) for commands and [HarnessQueries](../backend/src/harness/queries.py) for reads. A server process runs one command per work item at a time.
- Model turns run in the background. HTTP `POST /api/work-items/{item_id}/messages` returns `202` when it accepts a follow-up. HTTP `GET /api/work-items/{item_id}/activity` and MCP `work_item_activity` report `running`, `done`, or `failed`, with recent tool names and any error. Activity lives in memory for the life of the server process.
- `POST /api/work-items/{item_id}/retry` with a `node_id` retries a ready node whose first turn did not save a conversation.

## Graph and persistence

A project identifies a registered Git repository and groups work items. Creating a work item saves the opening message on its Goal Alignment entry node and starts its first turn. The graph tracks node status and edge approval separately. A pending node is ready if it is the entry node or has an approved incoming edge.

SQLAlchemy maps projects, work items, nodes, and edges to SQLite. The graph repository restores concrete nodes with their saved data and conversations. The nodes share a graph and model runtime. Each graph has a Git workspace for its work item.

The shared agent runner records Pydantic AI Harness `SpendLimits` events in SQLite as model responses arrive. Each record belongs to a graph node. The API exposes work-item and project usage totals, including tokens and estimated cost at API rates. For Codex subscription runs, that estimate describes equivalent API usage.

## Path implemented today

Goal Alignment creates a Technical Planning node. Technical Planning can create an Implementation node or multiple Goal Alignment nodes. Creation records destination nodes and pending edges. When the source creates a new set, the graph replaces its earlier unapproved destinations and keeps the approved history.

Approval identifies an edge by ID. The same request can edit the destination's input data before its first turn starts. A user can continue an existing conversation on a node that has not been superseded, including a completed node.

Rollback creates a pending edge to a completed predecessor. Approval makes that predecessor's existing conversation available again and marks its descendants superseded. Their history remains available. Closing a work item updates its status independently of the graph and Git.

## Agent context and Git

The [agent harness](../backend/src/harness/agents/harness.py) adapts Pydantic AI and restores the node's saved conversation. Each node supplies its own tools and builds its instructions and opening message.

- **Goal Alignment** can list, search, and read repository files at its Git baseline.
- **Technical Planning** receives the brief and can read files at its saved baseline.
- **Implementation** receives the brief, plan, and any feedback. It can read and edit files and saves the resulting commits on its branch.
- **Review** starts at the Implementation branch tip captured when the Review node is created. Its read and diff tools stay pinned to that commit.

Every node has a required `nodes.commit_sha` for its starting commit. The value stays fixed across turns. Each work item uses a checkout under `worktrees/items/` in the state directory and switches branches between nodes. An Implementation diff compares its starting commit with its branch tip. A Review diff compares the source Implementation's starting commit with Review's starting commit.
