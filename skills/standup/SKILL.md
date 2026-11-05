---
name: standup
description: "Generate the user's daily standup update from real activity: GitHub PRs and commits, unpushed local work across worktrees, and Claude/Codex/OpenCode session history. Use when the user says /standup, give me my standup, what did I do yesterday, or wants a status summary."
---

# Standup

Produce a short, spoken-ready standup update from real activity. Never invent items. A gathering script collects the raw material. The script only gathers. The summary is the skill's job.

## Step 0: Confirm the day scope

Propose the smart default, then ask the user to confirm. One question, three choices: today, previous workday, or both. Monday reaches back to Friday. A weekend run covers since Friday. Late-night work past midnight belongs to the standup that has not happened yet.

Translate the confirmed scope into explicit bounds. A single named day means that day's full cycle, 10:00 that day to 10:00 the next, so its late-night work stays attached.

## Step 1: Gather

Run `${CLAUDE_SKILL_DIR}/scripts/gather.py`. With no arguments it computes the default window from the current time and prints one JSON blob. Pass explicit bounds when the user confirmed a scope other than the default.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gather.py"
python3 "${CLAUDE_SKILL_DIR}/scripts/gather.py" --start 2026-09-05 --end 2026-09-06
python3 "${CLAUDE_SKILL_DIR}/scripts/gather.py" --start 2026-09-04
python3 "${CLAUDE_SKILL_DIR}/scripts/gather.py" --org myorg --repo-root /path/to/repo
```

A bare `YYYY-MM-DD` means 10:00 local that day. Use full ISO only for sub-day precision. `--org` overrides the auto-detected org from the git remote. `--repo-root` defaults to the current directory. The local scan covers that repo and all its git worktrees. `--no-github`, `--no-local`, and `--no-sessions` drop a source when asked. The `window` object in the output states exactly what was covered. Echo that range in the header.

Session history is best-effort across Claude, Codex, and OpenCode. Missing stores are skipped silently. Present stores never block the other sources.

## Step 2: Translate each item into plain words

Write for a **non-technical listener**: a manager, a product owner, a client. Every line answers two questions in everyday words. What changed for the people using the product, and why does that help them?

Before writing a line for an item you authored that has a PR (Done and In progress), read its PR body: `gh pr view <number> --repo <org>/<repo> --json title,body`. The body holds what the title compresses, namely the effect a user sees and any measured numbers. Carry one number across when the body states one, as a before and after a listener can feel: "opens in 0.04 s instead of 0.75 s", "about 17 times faster". Use only numbers the body states.

Work without a PR (pushed commits, unpushed commits, uncommitted changes, stashes, session-only tickets) gets its plain line from the gathered commit messages, branch names and session titles. Describe the effect those sources support and leave the number out.

Name the screen or task the user knows, then the effect. Translate every engineering term into what it does for the user: "fanout 1,013 to 14 queries" becomes "the Alternatives tab opens about 17 times faster on large orders"; "cached currency formatter" becomes "price screens load faster". When an effect has no plain description, use a short everyday comparison.

Teammates' items (Merged, Reviewed) get one plain phrase each, written from the title. Read the body only when the title alone is engineering shorthand.

## Step 3: Write the standup

Keep it short and flat. One ticket is one line. A whole standup reads aloud in about a minute. Never list individual commits or SHAs. Never dump file lists. Never quote session prompts verbatim.

Collapse every commit, PR, and local change for the same ticket into a single line. Branch names and PR titles carry the ticket number.

Four buckets, in this order. Omit any empty bucket.

- **Done.** PRs you authored that merged, plus your pushed commits. Say what landed, not that a PR merged.
- **Merged (N).** Teammates' PRs you merged, whether or not you reviewed them in the window. The heading carries the count.
- **In progress.** Open PRs and unpushed local work such as uncommitted changes, unpushed commits, and stashes. Use sessions only to name a ticket that had real work but left no commit yet. Skip anything already covered above.
- **Reviewed.** Teammates' PRs you reviewed but did not merge. One line total when few.

## Output format

Always output the standup in markdown, using this structure.

```markdown
## Standup — <window.start_readable> to <window.end_readable>

### Done

- **<screen or feature>**: <what changed for users>. <why it helps, with a number when the PR states one> (#<pr>)

### Merged (<n>)

- <teammate>'s <plain phrase for the change> (#<pr>)

### In progress

- **<screen or feature>**: <what is being changed and what users will get>

### Reviewed

- <teammate>'s <plain phrase for the change> (#<pr>)
```

Write each Done and In progress line as one or two short sentences. Lead with the screen or feature the listener knows, then the change, then the benefit. Merge small related items onto one line rather than spending a bullet each.

One line, written for the listener:

```markdown
- **Procurement, Alternatives tab**: opens about 17 times faster on large orders (0.04 s instead of 0.75 s) and no longer slows the system down for other users. Prices and totals are unchanged. (#7738)
```

When any of `github.errors`, `github.error`, `local.errors`, or `sessions.errors` is present, or a source was skipped, add one short note at the end so the user knows the picture is partial. Otherwise say nothing about plumbing. When everything is empty, say so in one line and suggest checking the org or repo root.
