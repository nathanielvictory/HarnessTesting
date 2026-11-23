# Harness architecture

This document describes the current implementation. See the [product description](product.md) for intended behavior and the [glossary](glossary.md) for shared terms.

## Entry points and application boundaries

- The **browser** uses React and TypeScript. It calls the FastAPI endpoints through the Vite proxy. The frontend owns project and work item selection, conversation display, and review controls. The backend returns the work item's graph and current node.
- **FastAPI and MCP** call the same [application service](../backend/src/harness/application.py) for catalog and work item operations. MCP exposes those operations over Streamable HTTP. The service permits one mutation per work item at a time within a server process.
- The **CLI** runs an interactive session and shares the catalog, graph repository, and work item operations with the server. It has its own terminal interaction and agent cancellation handling.
- [WorkSession](../backend/src/harness/operations/work_session.py) coordinates the operations for one work item. It chooses the next node for a given operation. The [traverser](../backend/src/harness/graph/traverser.py) invokes the operation and records the outcome and any resulting edge.

## Graph and persistence

A project identifies a registered repository and groups work items. Creating a work item creates its goal alignment entry node. The graph repository loads the item's nodes and edges into an in-memory graph. To find the current node, the graph starts at the entry node and follows recorded departures in order, consuming each edge once. An edge's order applies at its source node. That lets the graph revisit a node and distinguish its successive departures.

SQLAlchemy maps projects, work items, nodes, and edges to SQLite. The graph repository maps those records to the graph's Python objects and saves node state and transitions together. Agent-driven nodes can save their model, conversation, and node-specific data. Nodes can also save a branch ref and commit SHA. The API and MCP expose visible messages and graph history from this state.

## Path implemented today

The shipped path below is the baseline for dogfooding. The [first iteration design](product.md#first-iteration) calls for steering and approval inside each node, including implementation. The [automation design](product.md#as-automation-grows) covers independent agent review and human gates at the points where the developer needs to intervene.

Goal alignment and technical planning each collect a conversation and draft. Approving the brief records a Git baseline and advances to technical planning. Approving the plan advances to implementation. Once implementation returns a result, Harness opens a human review node.

At implementation review, the developer can accept the result, send feedback back to the same implementation node, revise the plan, or review an earlier brief or plan. Feedback resumes the saved implementation conversation. Revising an earlier decision creates a new node seeded with the previous approved text and the revision note. A subsequent implementation starts from the earlier baseline on a new branch. The graph retains the earlier path. Accepting implementation marks the work item complete and leaves the branch available for the developer to integrate.

The path is defined in Python and a plan leads to one implementation node at a time.

## Agent context and Git

The [agent harness](../backend/src/harness/agents/harness.py) adapts Pydantic AI and restores the node's saved conversation for a new turn. Each operation supplies its own agent profile and builds the prompt for the turn.

- **Goal alignment** uses its instructions and conversation. It has no repository file tools today.
- **Technical planning** receives the approved brief and reads the target repository from a detached worktree at the Git baseline.
- **Implementation** receives the approved brief and plan, plus review feedback when applicable. It can read and edit files in an assigned worktree. Harness creates any resulting commit and records the branch ref and SHA.

The implementation branch remains after the worktree is removed. That branch keeps its history reachable and provides a name for inspection or integration. On resumption, Harness checks that the branch still points to the saved SHA. Review transitions can also record the exact commit reviewed.
