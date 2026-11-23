# Harness glossary

## Organizing work

**Project** — The unit of organization for work on a Git repository. It groups work items and is the scope for guidance learned while working on them. A repository can have multiple projects, and a project can have multiple active work items.

**Work item** — A unit of work within a project, such as a feature, fix, investigation, or technical change. The user opens a work item to start or resume its graph. A work item can span several implementation and review steps.

## Process

**Graph** — The nodes and directed edges for a work item. It records where work began, which transitions occurred, and the steps available for resumption or inspection.

**Node** — An instance of a step in a work item's graph. A node has an action and can hold state such as a draft, conversation, or saved Git state.

**Action** — The kind of operation a node performs, such as goal alignment, technical planning, implementation, or human review.

**Edge** — A directed transition from one node to another. A recorded edge carries the outcome that led to the transition and its order among departures from the source node.

**Goal alignment** — The step where the user and agent agree on what the work should accomplish and what a satisfactory result looks like. The agreed description is the brief.

**Technical planning** — The step where the user and agent agree on how to deliver the brief, including whether to divide the work into smaller steps.

**Review** — A decision point after a step produces a result. Review can advance the work, send feedback to the same agent conversation, or revisit an earlier decision.

## Resuming and retrying

**Conversation** — The saved exchange associated with an agent-driven node. Resuming that node continues its conversation with the relevant context.

**Turn** — One invocation of an agent within a conversation, such as responding to user feedback. A node can have multiple turns.

**Implementation attempt** — A try at implementing an agreed scope from a chosen Git baseline. It can include several turns and rounds of review feedback. A clean retry starts a new attempt and leaves the earlier attempt available for inspection.

**Git baseline** — The commit chosen as the starting point for an implementation attempt.

**Saved Git state** — The branch ref and commit that identify where work was saved. The branch identifies the line of work to resume. The commit identifies the exact snapshot for resumption or inspection.

**Worktree** — The local checkout in which the harness or agent works on files.
