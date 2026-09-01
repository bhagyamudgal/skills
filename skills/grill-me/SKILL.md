---
name: grill-me
description: Grill the user on a plan, one question at a time, until every decision in its tree is resolved. Use when the user says "grill me", or passes a plan file to be interrogated.
---

Interview me relentlessly about every aspect of this plan. Walk down each branch of the decision tree, resolving dependencies between decisions one-by-one.

If invoked with a file path argument, Read that file first and use its contents as the plan to grill.

## Rules

**ALWAYS use the AskUserQuestion tool** for every question you present to the user. Every decision reaches the user as a cursor-selectable option.

- Before the first question, enumerate the open decisions in the plan as a numbered list and print it.
- Ask **ONE question at a time**: one AskUserQuestion call per turn, then wait for the answer.
- Provide **2-4 options** per question. Your recommended answer should be the **first option** with "(Recommended)" in the label.
- Each option needs a clear `description` explaining the trade-off or implication, not just a label.
- **After each answer**, briefly acknowledge the choice (1 sentence max), ending with `<n> of <total> resolved`, then present the next question.
- If an answer is non-committal ("not sure", "whatever you think", "both"), do not record it: restate the trade-off in one sentence and re-ask the same decision once. Record the second answer either way.
- When an answer contradicts an earlier one or leaves a dependency unresolved, say which one and re-ask before moving on.
- If a question can be answered by **exploring the codebase**, explore the codebase INSTEAD of asking the user. Use Grep, Glob, Read, or Agent to verify assumptions before grilling on them.
- If the user says "enough", "done", "stop", or "skip the rest", announce **"Grill complete."** with decisions captured so far and exit.
- When every numbered decision has a recorded answer and no answer has opened a new one, announce **"Grill complete."** with the numbered summary. If an answer opens a new decision, append it to the list and say so.
- If invoked with a file path, append the numbered decisions under a `## Decisions` heading in that file before announcing "Grill complete."
