---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

If invoked with a file path argument, Read that file first and use its contents as the plan to grill. Do not rely solely on conversation context — always read the plan from disk when a path is provided.

## Rules

**ALWAYS use the AskUserQuestion tool** for every question you present to the user. Never fall back to plain-text questions with "A/B/C" or "y/n" — every decision MUST be cursor-selectable via AskUserQuestion.

- Ask **ONE question at a time**. Never batch multiple decisions into one message. Never emit multiple AskUserQuestion calls in one turn.
- Provide **2-4 options** per question. Your recommended answer should be the **first option** with "(Recommended)" in the label.
- Each option needs a clear `description` explaining the trade-off or implication — not just a label.
- **After each answer**, briefly acknowledge the choice (1 sentence max) before presenting the next question. This prevents a rapid-fire feeling and confirms the decision was captured.
- If a question can be answered by **exploring the codebase**, explore the codebase INSTEAD of asking the user. Use Grep, Glob, Read, or Agent to verify assumptions before grilling on them.
- If the user says "enough", "done", "stop", or "skip the rest", announce **"Grill complete."** with decisions captured so far and exit.
- When all decision branches are resolved, announce **"Grill complete."** with a numbered summary of all decisions captured.
