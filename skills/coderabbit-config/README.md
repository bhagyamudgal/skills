# CodeRabbit config bootstrap

Two files — copy them, customize, and CodeRabbit absorbs ~80% of the style + convention findings that `/review-pr` was doing manually before.

## Files

- **`coderabbit.yaml.template`** — drop into a repo as `.coderabbit.yaml`. Encodes path-based instructions for TypeScript, React, tests, performance, migrations, SQL.
- **`coderabbit-learnings.md`** — copy-paste-ready learning blocks for the CodeRabbit dashboard or PR comments. Persists org-wide.

## Bootstrap a repo

```bash
cp ~/.claude/skills/coderabbit-config/coderabbit.yaml.template <repo>/.coderabbit.yaml
cd <repo>
# Customize: comment out path_instructions blocks that don't apply (e.g., remove migrations block for non-SQL projects)
git add .coderabbit.yaml
git commit -m "chore: add coderabbit config"
git push
```

CodeRabbit picks up the file on the next PR.

## Add learnings (one-time, org-wide)

Pick ONE of these — both end up in the same place (CodeRabbit's cloud):

### Option A — web UI (fastest for bulk paste)

1. Visit https://app.coderabbit.ai/learnings.
2. Click **Add learning**.
3. Paste each block from `coderabbit-learnings.md` separately (one learning per block — the `## Heading` blocks are a guide for organization, paste only the body text).
4. Set **Scope** to `Global` so all repos in your org benefit.

### Option B — PR comments (dripped over time)

In any PR, comment:

```
@coderabbitai add learning: <paste a block's body text>
```

CodeRabbit confirms and stores the learning. Useful when a real PR surfaces a convention you want enforced going forward.

## Per-project customization

The template is a generic starting point. Common edits:

| Project type | Edit |
|---|---|
| Pure backend (NestJS, Express) | Remove the `**/*.tsx` block; keep TS + tests + perf + tryCatch. |
| Pure frontend (Next.js, no API) | Remove the `**/migrations/**` and `**/*.sql` blocks. |
| Non-monorepo | Change `{apps,packages}/**` to `src/**`. |
| Solo / no team | Remove `tone_instructions` (the assertive default is fine). |
| Heavy SQL repos | Add a stricter `**/*.sql` block with team-specific column-naming or migration rules. |

## How this complements `/review-pr`

Once `.coderabbit.yaml` is in place, CodeRabbit catches:
- Style violations (any, !., as, type-vs-interface, function keyword)
- Magic numbers, boolean naming, nested ternaries
- React anti-patterns (useEffect for derivation, state in useEffect)
- Performance basics (sequential awaits, N+1, missing indexes)
- File-size warnings
- SQL/migration risks

`/review-pr` then focuses on what only deep semantic + codebase-wide work can do:
- **Q1 Intent** — does the PR solve the linked issue's goal? (domain knowledge)
- **Q6a Reusability** — does the diff reimplement something already in `packages/` or `apps/`? (codebase-wide grep)
- **Multi-round state** — has this finding been resolved/dismissed in earlier rounds?
- **Anti-slop critic-pass** — verify file:line references, drop hallucinations, downgrade unverified library claims

## Verify CodeRabbit picked up the config

After committing `.coderabbit.yaml`, open or update a PR. CodeRabbit's review walkthrough comment should reference your path instructions. If it doesn't:

```bash
gh pr view <url> --json comments -q '.comments[].body' | grep -i coderabbit
# Or check the CodeRabbit dashboard's "Reviews" tab for that PR
```

Common gotchas:
- **YAML indentation**: 2 spaces, no tabs. The template is correct; don't reflow it.
- **`profile: assertive`**: this is intentional — `/review-pr`'s critic-pass filters out the noise. If you find CodeRabbit too noisy without `/review-pr`, switch to `chill`.
- **`auto_review.drafts: false`**: drafts are skipped to save quota. Toggle to `true` if you want CodeRabbit on every push.
