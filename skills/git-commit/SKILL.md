---
name: git-commit
description: Write a conventional commit. Use when the user asks to commit, or asks for a commit message to run themselves.
license: MIT
allowed-tools: Bash
---

# Git Commit with Conventional Commits

Analyze the actual diff to determine type, scope, and message. Never write the message from memory of the task.

## Message-Only Mode

When the user asks FOR a commit message ("give me a commit message", "commit message suggestion") rather than asking TO commit: analyze the diff as usual and print two variants for them to run — a one-liner and a detailed one.

## Workflow

### 1. Analyze Diff

```bash
git diff --staged        # if files are staged
git diff                 # if nothing staged
git status --porcelain
```

**Every file in `git status --porcelain` is classified into exactly one commit** before you write a message. A mixed diff becomes several commits, not one vague message.

### 2. Stage Files

Stage only files you have read in the diff. `.env`, `credentials.json`, and key files stay unstaged.

When the caller supplies a **Verified content snapshot**, record the branch, old head, and original index tree, then build the candidate commit in a disposable detached worktree at that head. Load the verified tree into that worktree's index and files, require `git write-tree` to equal the snapshot, and run the ordinary commit there so every hook still runs. Require the candidate commit's `HEAD^{tree}` to equal the snapshot; a hook failure or mismatch leaves the real branch untouched. Only after that match, require the original index tree to remain unchanged, atomically advance the recorded branch from the recorded old head to the candidate commit, refresh the original index from that commit without changing its worktree, and remove the disposable worktree. A changed index, failed old-head guard, or cleanup is reported; never create the candidate commit on the real branch or restage its live worktree.

### 3. Generate Commit Message

From the diff, determine the **type**, the **scope** (the area or module affected), and the **description**.

Subject: imperative, under 72 chars, explaining WHY rather than WHAT — the diff already shows what. Body uses `-` bullets for key changes, 3-5 max.

### 4. Commit

```bash
# Single line
git commit -m "<type>[scope]: <description>"

# Multi-line — one quoted -m string, newlines inside the quotes
git commit -m "<type>[scope]: <description>

<optional body>

<optional footer>"
```

One atomic change per commit.

Every git operation here is **append-only** — stage, commit, and if a hook fails, fix it and land a new commit on top rather than amending.

Four things sit outside that word and need saying: leave `git config` alone, let hooks run (no `--no-verify`), keep `--force` and hard resets behind an explicit request, and never force-push `main`.
