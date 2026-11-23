# Dogfooding work item candidates

Use these notes to seed work items in Harness. The durable product description is in [docs/product.md](../docs/product.md).

- [x] **Build the initial web app.** Provide a React frontend and a FastAPI backend for selecting projects and work items, talking with agents, and reviewing results.
- [ ] **Make nodes inspectable and editable.** Show the instructions, inputs, and tool access each node receives. Make it easy to revise a node, change what it can see or do, and add or remove nodes as we learn what helps.
- [ ] **Execute multi-step plans through the graph.** Keep one work item for the overall requirement. Review each implementation step before advancing. Each implementation gets its own worker conversation and starts from the accepted commit of the work it depends on.
  - **Break down work before implementation.** When an implementer finds that a step is still too broad, send the proposed split through another alignment and planning pass. A child step can be split again until the scope is reasonable. The parent waits for the reviewed child results.
  - **Break down work after an attempt.** Review feedback can continue the same conversation, start a clean retry, or return to the alignment or technical plan that defined the step. The revised plan can split the step into multiple child steps. Keep the previous attempts, feedback, and Git states available while choosing where to restart.
  - **Define the handoffs.** Work through when to split, which parent step waits, what a child receives and returns, and which accepted checkpoints can be reused after revising a plan.
- [ ] **Give goal alignment and technical planning the context they need.** Supply the project and work item, the current node and its role, what approval leads to, and relevant earlier decisions. Extend read-only access to goal alignment so both node types can consult the repository's docs and code.

Start with an opinionated development flow that carries this context forward automatically. Use repeated corrections to improve the default instructions and handoffs so the user can focus on the decisions specific to each work item.
