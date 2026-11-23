# Harness glossary

These definitions describe how we intend Harness to work as we start using it on its own development.

## Organizing work

**Project** — The unit of organization for work on a Git repository. It groups work items and is the scope for guidance learned while working on them. A repository can have multiple projects, and a project can have multiple active work items.

**Work item** — A unit of work within a project, such as a feature, fix, investigation, or technical change. The user opens a work item to start or resume its graph. A work item can span several implementation and review steps.

## Process

**Graph** — The nodes and directed edges for a work item. It records where work began, which transitions occurred, and the steps available for resumption or inspection.

**Node** — An instance of a step in a work item's graph. A node has a type and can hold state such as a draft, conversation, or saved Git state. An agent-driven node can involve multiple turns of discussion and revision.

**Node type** — The category of a node. Its type defines what the node does. We may add, revise, or remove node types as we learn how to run the process. The graph determines how those nodes are connected and traversed.

**Edge** — A directed transition from one node to another. A recorded edge carries the outcome that led to the transition and its order among departures from the source node.

**Rollback** — Returning to an earlier point in the graph to reconsider a decision or resume work from its saved state. The previous path remains available, including what we learned along the way, so it can inform the next decision.

## Intended node types

**Goal alignment** — The user and agent agree on what the work should accomplish and what a satisfactory result looks like. The agreed description is the brief.

**Technical planning** — The user and agent agree on how to deliver the brief, including whether to divide the work into smaller pieces.

**Implementation** — The agent makes the planned changes from the chosen Git baseline. The user can discuss findings and request adjustments across multiple turns before approving the result.

**Code review** — Examines the code changes against the agreed brief, plan, and relevant project guidance. A human initially reviews the changes during implementation. As the process matures, a dedicated node can use an agent with a fresh conversation to review the result and send findings back to implementation.

**Human review gate** — Asks a human operator to inspect a result or make a judgment before the graph advances. It can be used wherever a decision calls for human involvement, including accepting a change, requesting revisions, or revisiting an earlier decision.

### Human involvement

Initially, the user participates synchronously and approves the exit from each node. The user can give feedback within the current node while the work is underway. As we learn where this involvement helps, we can automate individual steps and reserve dedicated human review gates for decisions that benefit from an operator.

When a node has multiple available transitions, the user chooses which one to take. As we automate the process, the subagent running the node can select from those transitions where that decision has been delegated.

## Resuming and retrying

**Conversation** — The saved exchange associated with an agent-driven node. Resuming that node continues its conversation with the relevant context.

**Git baseline** — The commit recorded at work item creation for goal alignment, technical planning, and the start of implementation.

**Saved Git state** — The branch ref and commit that identify where work was saved. The branch identifies the line of work to resume. The commit identifies the exact snapshot for resumption or inspection.

**Worktree** — The local checkout in which the harness or agent works on files.
