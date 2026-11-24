# Harness ideas

## Approve a plan with a revision

Let the developer add a sentence of feedback when approving a technical plan, such as asking for more emphasis on one part of the work. Save the approval immediately and pass the plan and feedback together to implementation. The feedback is part of what the developer approved, so this takes a single approval action with no additional planning turn.

## Edit a draft directly before approval

Let the developer edit the draft text and approve the edited version. This gives the developer direct control when they already know what they want to change. The saved approval should contain the exact text they approved and pass it to the next node.

## Research node

Let a developer, or eventually an automated reviewer, take a short detour from the current node to ask a focused question. A research agent could read the relevant parts of the repository or use web search when the question calls for it. Give the agent a separate conversation and bring a concise answer with relevant sources back to the originating node. That keeps the research turns out of the conversation the developer or reviewer is trying to resume.

Start with the existing GPT-6.2 Sol model. Later, try a smaller, faster model such as Luna for focused questions and evaluate the web search tools available through Pydantic AI.
