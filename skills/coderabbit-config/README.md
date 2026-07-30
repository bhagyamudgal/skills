# CodeRabbit config bootstrap

**CodeRabbit is the sieve; `/review-pr` is the critic-pass.** The sieve catches style, convention, and standard-pattern findings so the critic-pass only ever sees what needs judgement.

## Files

- **`coderabbit.yaml.template`** — drop into a repo as `.coderabbit.yaml`. Encodes path-based instructions for TypeScript, React, tests, performance, migrations, SQL.
- **`coderabbit-learnings.md`** — copy-paste-ready learning blocks for the CodeRabbit dashboard or PR comments. Persists org-wide.

The seam between them: rules that attach to a file glob live in the yaml; rules that cannot live in the learnings.

## Bootstrap a repo

```bash
npx skills add bhagyamudgal/skills@coderabbit-config
cp ~/.claude/skills/coderabbit-config/coderabbit.yaml.template <repo>/.coderabbit.yaml
cd <repo>
# Customize: comment out path_instructions blocks that don't apply (e.g., remove migrations block for non-SQL projects)
git add .coderabbit.yaml
git commit -m "chore: add coderabbit config"
git push
```

CodeRabbit picks up the file on the next PR.

The template's first line is a `yaml-language-server` schema pragma — a malformed config shows up as an editor squiggle before you commit it.

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

| Project type | Edit |
|---|---|
| Pure backend (NestJS, Express) | Remove the `**/*.tsx` block; keep TS + tests + perf + tryCatch. |
| Pure frontend (Next.js, no API) | Remove the `**/migrations/**` and `**/*.sql` blocks. |
| Non-monorepo | Change `{apps,packages}/**` to `src/**`. |
| Solo / no team | Remove `tone_instructions` (the assertive default is fine). |
| Heavy SQL repos | Add a stricter `**/*.sql` block with team-specific column-naming or migration rules. |

## Gotchas

- **`profile: assertive`**: `/review-pr`'s critic-pass filters out the noise. If you use CodeRabbit without `/review-pr`, switch to `chill`.
- **`auto_review.drafts: false`**: drafts are skipped to save quota. Toggle to `true` if you want CodeRabbit on every push.
