---
name: grill-me
description: Grill the user on a plan, one question at a time, until every decision in its tree is resolved. Use when the user says "grill me", or passes a plan file to be interrogated.
---

Interview me relentlessly about every aspect of this plan. Walk down each branch of the decision tree and settle dependencies between decisions one by one. I would rather get grilled now than rebuild later.

If I invoke you with a file path argument, read that file first and grill its contents as the plan.

## Rules

Always use the AskUserQuestion tool for every question you present to me. Every decision reaches me as a cursor-selectable option.

- Before the first question, enumerate the open decisions in the plan as a numbered list and print it.
- Ask decision zero first: is this approach even right. Offer one credible alternative drawn from the codebase or the issue, and grill it before the rest.
- Ask one question at a time. Make one AskUserQuestion call per turn, then wait for my answer.
- Give 2-4 options per question. Put your recommended answer first with "(Recommended)" in the label.
- Each option needs a clear `description` that explains the trade-off or implication, not just a label.
- State each question in plain words with one line of context, then give one concrete example before the options. Never ask a bare technical question.
- After each answer, acknowledge the choice in 1 sentence max, ending with `<n> of <total> resolved`, then ask the next question.
- If my answer is non-committal, something like "not sure" or "whatever you think" or "both", do not record it. Restate the trade-off in one sentence and re-ask the same decision once. Record the second answer either way.
- When an answer contradicts an earlier one or leaves a dependency unresolved, say which one and re-ask before moving on.
- If you can answer a question by exploring the codebase, explore it instead of asking me. Use Grep, Glob, Read, or Agent to verify assumptions before grilling me on them.
- If I say "enough" or "done" or "stop" or "skip the rest", post per the issue rule below with the decisions captured so far, then announce "Grill complete." and exit.
- When every numbered decision has a recorded answer and no answer has opened a new one, announce "Grill complete." with the numbered summary. If an answer opens a new decision, append it to the list and say so.
- If I invoked you with a file path, append the numbered decisions under a `## Decisions` heading in that file before announcing "Grill complete."
- If a GitHub issue was provided in context as a URL, number, or issue body, post an issue comment for tracking before announcing "Grill complete." The body holds the numbered decisions followed by the full plan, or whatever decisions are captured so far on early exit. Comment on the exact issue from context with `gh issue comment <url> --body`. When context holds only a number, resolve its repository first instead of assuming the checkout.
