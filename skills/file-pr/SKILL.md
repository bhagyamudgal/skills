---
name: file-pr
description: Open a GitHub pull request whose title and body a reviewer understands in one read. Use when opening a PR, pushing finished work for review, or filing a PR for a completed branch — never open one by hand.
---

# File a Pull Request

A PR is read by someone who has not seen the session, the diff, or the ticket. Every bar below exists so that reader understands the change in one pass.

## 1. Check preconditions

Read the branch, the completion report, and the scope of the diff.

- **Branch** — `git rev-parse --abbrev-ref HEAD` satisfies the branch-naming rule in `CLAUDE.md`. Rename a harness-generated name under that rule before filing.
- **Completion** — `done` already reported overall completion verified for this work. Check its report; do not re-run it here, and do not substitute your own judgement for a missing one. No report means no PR.
- **Scope** — every file in `git diff <base>...HEAD --stat` traces to what was asked. Anything outside it is the stop-and-ask case in `CLAUDE.md`, not a caveat in the body.

**Gate:** branch, completion, and scope each have a recorded result, and a failed one stops the PR rather than being disclosed in it.

## 2. Resolve the base branch and the issue link

```bash
gh repo view --json defaultBranchRef -q .defaultBranchRef.name
git branch -r --list 'origin/dev*' 'origin/develop*'
```

The default branch is not automatically the base. When the repo has an active integration branch, that is the base.

Choose exactly one issue link:

- The diff fully resolves the issue — `Closes #N`
- It resolves part of one, a sub-task of an umbrella ticket or one slice of an epic — `Refs #N`, plus one line naming which part it covers and what stays open
- It was found while investigating an issue but does not fix it — `Refs #N`, and say that in the body

Never `Closes` an issue this diff does not finish.

**Gate:** the base branch and the issue link each come from command or issue output, not from assumption.

## 3. Compose the title

Form: `<type>(<module>): <description>`. Name the module the way it reads on the board, not the way the directory spells it.

The description names what someone **observes** — what broke, or what is now possible. Not what you edited.

Banned as the whole description: `improve`, `update`, `handle`, `refactor`, `fix logic`, `clean up`, `various fixes`.

| Mechanism — rewrite | Outcome — ship |
|---|---|
| `fix(portions): correct filter logic` | `fix(portions): portion totals skipped orders placed after cutoff` |
| `feat(auth): update session handling` | `feat(auth): stay signed in across browser restarts` |

**Tell:** name who observes the thing in the title. When the only honest answer is "someone reading the diff", the title names a mechanism — rewrite it.

**Gate:** the observer is named, and no banned word stands as the description.

## 4. Compose the body

Open with two to four sentences of plain prose answering **what was wrong, then what changed** — written to make sense to someone who never opens the diff. No heading above it, never a bullet list, never optional.

Then only the sections that carry real content:

- **What changed** — one bullet per meaningful change, each naming its effect rather than its file
- **How to verify** — what you actually ran and what it printed, or the steps a reviewer follows. A check that could not apply to this change is named not applicable alongside the validation that ran in its place.
- **Risk or scope notes** — only when something is genuinely uncertain, migrated, or deliberately deferred
- The issue link from section 2

A heading with nothing under it comes out. A small PR is the lead paragraph, how to verify, and the link.

The human-authored rule in `CLAUDE.md` governs the body's voice and its ban on agent, pipeline, and session references.

**Gate:** the lead paragraph stands alone without the diff, and every heading present carries content.

## 5. Cold-read the result

Read the composed title and body once as someone with no session context. Name a result for each bar:

- **Title** — who observes it
- **Lead** — states what was wrong and what changed, without the diff
- **Terms** — every file, flag, or term is introduced where it first appears
- **Back-references** — no "as mentioned", "the above", "the earlier issue"
- **Verification** — describes what ran, not what should work
- **Voice** — no stock phrases, no agent or session references

A bar you did not name is a bar you did not check. A failed bar is rewritten and re-read, never shipped as a noted exception.

**Gate:** all six bars have a named result and none is failing.

## 6. Open it

```bash
git push -u origin <branch>
gh pr create --base <base> --title "<title>" --body "<body>"
```

Print the URL. Never merge — opening the PR ends the autonomy and hands review to a human.

**Done:** the three preconditions held, the base and issue link came from real output, the title names an observer, the body opens with a standalone lead, all six cold-read bars are named and clean, and the PR URL is printed.
