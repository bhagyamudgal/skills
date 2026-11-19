---
name: grill-me
description: Grill the user on a plan one question at a time until every decision is settled, then check the plan's facts against the codebase. Use when the user says "grill me", "harden", "check" or "verify" a plan, or passes a plan file to be interrogated.
---

Interview me relentlessly about every aspect of this plan. Walk down each branch of the decision tree and settle dependencies between decisions one by one. I would rather get grilled now than rebuild later. Once the decisions are settled, prove every fact they rest on and attack the plan before I code.

If I invoke you with a file path argument, read that file first and grill its contents as the plan. If the decisions are already settled and I ask only for verification, skip to the verification pass below. The challenge pass still follows it.

## What counts as checked

Every fact you state to me is a claim, wherever it appears: the settled list, a question's context line, an option's description, an example, or the plan itself. A claim is checked when you observed it with a tool in this session. The issue text, the plan, a subagent's summary, a symbol's name, and your memory of the code are leads to follow.

| Kind | Looks like | Proof |
|---|---|---|
| Exists | a path, symbol, flag, command, CI job | Open it at the cited line. |
| Behaves | "X already blocks, handles, always, never does Y" | Read every path that reaches X: each caller, each writer, each entry point. Name the case most likely to break the claim and check that case. Run it when a test, query, or command can show the result. |
| Absent or complete | "no X exists", "these are all the sites", "that cast is gone" | Search the whole repo for what the thing does under at least two patterns, beyond the name the ticket uses. Run each pattern against a known hit first, so an empty result means absent and not a broken pattern. |
| Number | a count, size, duration, rate | Compute or measure it from the source: a local database, the logs, the browser, a script. Label anything else an estimate. |
| Works | an option you offer, the approach you recommend | Name the one fact it cannot work without and observe it in the code or system that has to cooperate. |

A command that errors or prints nothing is no observation. State a claim you could not check as unverified and name what would check it.

## Rules

Ask every question through the AskUserQuestion tool, so each decision reaches me as a selectable option.

- Before the first question, read the code the plan touches and check the files, symbols, and behavior its decisions rest on. Then enumerate the open decisions as a numbered list and print it. Leave out any decision the code already settles and the plan does not change, and name the `file:line` that settled it.
- When the open list holds more than 10 decisions, group them by area and offer to settle a whole group in one answer.
- Ask decision zero first: is this approach even right. Offer one credible alternative drawn from the codebase or the issue, and grill it before the rest.
- Ask one question at a time. Make one AskUserQuestion call per turn, then wait for my answer.
- A chat reply I type while a question is pending is my answer to it. Record it and move on.
- Give 2-4 options per question. Put your recommended answer first with "(Recommended)" in the label.
- Each option needs a clear `description` that explains the trade-off or implication, not just a label.
- State each question in plain words with one line of context, then give one concrete example before the options. Never ask a bare technical question.
- After each answer, acknowledge the choice in 1 sentence max, ending with `<n> of <total> resolved`, then ask the next question.
- If my answer is non-committal, something like "not sure" or "whatever you think" or "both", do not record it. Restate the trade-off in one sentence and re-ask the same decision once. Record the second answer either way.
- When an answer contradicts an earlier one or leaves a dependency unresolved, say which one and re-ask before moving on.
- Ground every question before asking it. Check each claim in its context line, its example, and its options to the proof its kind needs. Check each option against the project's written rules in CLAUDE.md or AGENTS.md and name any rule it breaks. When the code answers the question and the plan does not propose changing that behavior, record that answer with its `file:line` and move on without asking. Otherwise build the options and the recommendation from what you found, and cite the `file:line` in the context line. When no code bears on the decision, say so in the context line.
- When a local database, a log, run history, or a browser measurement would settle the choice, read it before you pick the recommended option and put the figure in the context line. Ask before you connect to anything live.
- When a check corrects a fact behind a decision I already answered, say what was wrong and re-ask that decision with the corrected fact.
- If I say "enough" or "done" or "stop" or "skip the rest", make no new checks. Print the ledger for the decisions so far, marking `unverified` each row that lacks the proof its kind needs, and list each pass, lens, and recheck left unfinished. Append per the file rule and post per the issue rule below with the decisions, that ledger, and that list, then announce "Grill complete." and exit.
- Every "Grill complete." announcement ends with a `Pending on you:` line that names each decision, action, or decision-critical `unverified` row still waiting on me, or reads `Pending on you: nothing`.
- When every numbered decision has a recorded answer and no answer has opened a new one, move to the verification pass below. If an answer opens a new decision, append it to the list and say so.

## Verification pass

- Print the claim ledger: one numbered row for every claim the plan or a recorded decision rests on. Take rows from the plan, the settled list, and the context line, example, and options of every answered question. Each row holds the claim, its kind, its proof, and a result of `holds`, `corrected`, or `unverified`.
- Fill each row's proof with the observation its kind needs: the command you ran or the `file:line` you read, and what it showed. An earlier read counts when it already met that bar. Otherwise make the observation now.
- Fix what you can verify without asking, and say what you changed in one line each.
- Hand the decision-critical rows to one fresh agent that has not seen this conversation. A row is decision-critical when a recorded decision would change if it were false. Give it each row as a neutral question, so "no retry exists on the upload path" becomes "is there any retry on the upload path?". Add the proof rule for the row's kind and the repo path. Withhold your answer, your proof, and the decision the row supports. Ask what it observed and where, row by row.
- Reconcile its report with the ledger. Where its observation disagrees with yours, make the observation that tells the two apart, then correct the row. With no agent tool, mark the ledger `no independent recheck`.
- Ask about only what you cannot resolve on your own. Ask it under the same rules as a decision question.
- Never ask me to confirm a fact you could have checked.
- When a decision is re-asked, here or in the challenge pass, add the new answer's claims to the ledger and check them.
- The pass is done when every row reads `holds`, `corrected`, or `unverified`, the fresh agent's report is reconciled or the ledger is marked `no independent recheck`, and the final ledger is printed. Then move to the challenge pass.

## Challenge pass

Attack the plan the way its reviewer will. Work through each lens and print what you observed under it.

- **Premise.** Print one line per decision: the fact it cannot work without, and where you observed it. Look for that fact outside the code the plan changes, in whoever has to act for the decision to do anything: a user, a caller, an agent, another service. Drop any decision that exists only because of a decision whose premise failed, name each one you drop, and correct the total.
- **Regression.** For each piece of code the plan changes, list every other path that reaches it: callers, other entry points, other writers, other screens, tests that pin today's behavior, open PRs on the same files. Say what happens to each.
- **Gaps.** For each new behavior, walk the states no question covered: empty, deleted, filtered out, pending, unauthorized, a second locale or theme. In each state, take the action the plan is about, follow the plan's rule to what the user ends up seeing, and check it against the reason the plan exists. A state where the original problem comes back, or a new one appears, becomes a new decision.
- **Direction.** Say whether a smaller plan reaches the same result and whether the change improves the product for its user, from data when data exists.

A finding that changes a decision reopens it as a question under the same rules. After my answer, rerun each lens the new answer affects. When every decision has its premise line, every lens is printed, the ledger is reprinted with any new rows, and no decision is open, close out.

## Close out

- If I invoked you with a file path, append the numbered decisions and the verified corrections under a `## Decisions` heading in that file.
- If the context holds a GitHub issue as a URL, number, or issue body, post an issue comment. The body holds the numbered decisions and the verified corrections followed by the full plan, or whatever is captured so far on early exit. Comment on the exact issue from context with `gh issue comment <url> --body`. When context holds only a number, resolve its repository first instead of assuming the checkout.
- Then announce "Grill complete." with the numbered decisions, the corrections, every row still `unverified`, and `no independent recheck` when the ledger carries it.
