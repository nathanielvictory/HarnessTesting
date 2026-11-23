# Harness product

## Purpose

Harness is a local tool for developers who want to direct and improve how they work with coding agents. A developer supplies the goal, makes the decisions that require judgment, and reviews the work. Harness carries the agreed context between nodes, coordinates agent work, and records what happened. The aim is to spend less time repeating instructions and recovering from decisions that turned out to be wrong.

The first user is a developer using Harness to build Harness. The same process should work against other repositories, whose code, domain, and conventions may differ. See the [glossary](glossary.md) for shared terms.

## First iteration

A developer opens a project and starts or resumes a work item. Each project can have several active work items. Each item has a graph that records how the work progressed and gives the developer a place to pick it back up.

Working through the graph should feel like moving between focused Codex chats. Each agent receives instructions, tools, and context for its node, including the relevant project docs and earlier decisions. The developer can follow the agent's work, ask questions, and steer across multiple turns. During implementation, they can review changes and request adjustments in the same conversation. The developer approves each node's exit and chooses among available transitions.

The graph connects those conversations and decisions to saved Git states. When work exposes a bad assumption, the developer can follow the edges to see where the decision was made and why. They can choose a rollback point, reopen the relevant conversation with what they learned, and try a revised brief or plan from the appropriate Git state. The earlier path remains available for inspection.

## As automation grows

1. **Agree on the product outcome.** Goal alignment produces a brief the developer approves. From there, Harness can delegate technical planning, implementation, and routine approval decisions. A plan can divide the work into smaller pieces, and each piece can be divided again when needed.
2. **Implement and review the pieces.** A review agent starts a fresh conversation with the changes, brief, plan, and relevant project guidance. It can send findings back to implementation for another turn, approve the result, or trigger a rollback when an earlier decision needs revisiting. Over time, automated review should catch recurring problems so the developer can focus on subtler design choices.
3. **Return to the developer before completion.** A human review gate at the work item level brings the result back to the developer with the original brief and the path taken. If it meets the brief, the developer can accept it. If a small patch is enough, they can start another implementation node with focused feedback. They can also roll back one or more nodes, reopen technical planning, or return to goal alignment if the brief itself needs to change.
4. **Move review closer to the hard decision when needed.** The developer can review a particular piece of work, revisit its planning or alignment, or steer an individual implementation node directly. Straightforward work can reach the final gate in one pass. Difficult work can get as much direct steering as it needs, with Harness handing off context and Git state at each node.

## What Harness and the repository each own

Harness keeps work in progress and the history needed to resume it or learn from it. That includes drafts, decisions, conversations, feedback, transitions, and the saved Git states associated with the work. Completed items leave the active list and remain available for review.

The target repository is the durable entry point for its code, product definitions, domain vocabulary, and development practices. It can hold documentation directly or link to an authoritative source. When accepted work changes a durable agreement, updating the relevant project docs is part of completing the work.

## Dogfooding scenarios

- **Resume after an interruption.** Pause one work item, work on another, and return to the first with its brief, conversation, and saved Git state available.
- **Reconsider a plan after seeing the code.** Request a small adjustment in the same implementation conversation. If the issue traces back to the plan or brief, return to that decision, revise it using what was learned, and retry from a chosen Git state. The earlier work remains inspectable.
- **Deliver a larger change in pieces.** Agree on a plan, implement and review one piece at a time, and split a piece further when needed. If a later piece exposes a problem in an earlier decision, revisit that decision and choose which accepted work still applies.
- **Improve the process using real feedback.** Compare where the developer intervened across several work items and see whether a change to project guidance or the process reduces repeat corrections.

## Retrospectives

After enough work items to see a pattern, review where the developer intervened, which corrections recurred, and which nodes helped. Look at what each agent received, what it did, and which decisions led to retries or rollbacks. A recurring issue in one project can become guidance for that project's implementation and review agents. A pattern across projects can inform changes to the harness itself, including its nodes, transitions, instructions, and handoffs. The mechanism for supplying project guidance can evolve as we learn which context helps.

The first measure of success is whether we can build Harness with Harness while doing less repeated steering and still understanding how we reached each result. A small Android app is planned as a separate trial on another project.
