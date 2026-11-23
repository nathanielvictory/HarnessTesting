# Software development harness

We’re building a local, project-independent harness for running and improving an LLM-assisted software development process. The user directs the work and orchestrates the process. The harness coordinates the steps, supplies the context each step needs, and records what happened so the user and an agent can review and refine the process together.

The workflow is an editable graph. Each node can carry its own instructions, inputs, and outputs, and we can add, remove, or revise nodes and their connections as we learn. Goal alignment is one possible node. Its output captures the agreed description of the work and what success looks like. The harness can attach that output to the work item and pass it into later prompts, so an interruption, rollback, or fresh attempt can start from the current agreement. This conversation and the harness implementation give us a first workflow to observe and turn into repeatable steps.

The user can talk directly with a coordinating agent. The harness can also launch agents for dedicated tasks with scoped instructions and selected context. We’ll start with a few reusable steps for work such as discovery, design, implementation, and review, then see which steps earn their place.

The target repository owns its code, durable product and domain definitions, and documentation. The harness tracks active work such as features, changes, and investigations. When work is complete, the code is merged, durable documentation is updated as needed, and the item leaves the active stack. Past attempts, instructions, outcomes, and feedback remain available for review.

Isolated local workspaces make it possible to pause or branch work and explicitly choose which changes to integrate. When an implementation misses the mark, the default is to capture the feedback, revise the relevant inputs, and try again from a clean baseline. The prior attempt remains available for review. The workflow should also accommodate separate lines of work that can be completed and integrated independently.

The goal is to reduce repeated steering while keeping the process understandable and easy to change. Each project starts with a shared workflow and instruction set. Review feedback helps us identify which steps help, where the user repeatedly has to intervene, and what guidance should be refined for that project. We’ll use a simple Android app as the first end-to-end trial.
