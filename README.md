# Skills

Custom Claude Code skills for development workflows — code review, TypeScript fixes, QA automation, PR reviews, design direction, and coding discipline (code reuse + backend performance).

## Install

```bash
# Install all skills
npx skills add bhagyamudgal/skills

# Install a specific skill
npx skills add bhagyamudgal/skills@done

# List available skills
npx skills add bhagyamudgal/skills -l
```

## Update

```bash
# Update all installed bhagyamudgal/skills to the latest version
npx skills update

# Or use the upgrade alias
npx skills upgrade

# Update a specific skill
npx skills update bhagyamudgal/skills@review-pr

# Restrict to project- or user-level scope
npx skills update --project    # only project-level skills
npx skills update -g           # only user-level (~/.claude/skills/)
npx skills update -y           # skip scope prompt; auto-detect from cwd
```

`update` only refreshes skills you already have — it will not pick up a newly added one. Run `add` for those.

If anything looks wedged, remove and re-add:

```bash
npx skills remove bhagyamudgal/skills -s '*' -y
npx skills add bhagyamudgal/skills
```

## Skills (slash commands)

| Skill | Description |
|-------|-------------|
| `done` | MANDATORY post-task verification — six blocking steps: type-check, parallel review to zero critical/serious, simplify + blocking comment scan, correctness against the request, roll-call report, commit |
| `parallel-review` | Build a reviewer roster, dispatch it in parallel over a local diff, and merge to one ranked list — the merge is not done while any reviewer is outstanding |
| `review-pr` | Deep anti-slop review of a GitHub PR with critic-pass filtering, persistent multi-round state, and rolling-review posting — batch mode reviews multiple PRs via one subagent per PR with a consolidated report |
| `fix-pr-review` | Triage and fix CodeRabbit / `review-pr` findings, then reply + resolve PR conversations |
| `audit-ticket` | Audit a stale GitHub issue against current code — per-requirement verdicts with file:line evidence that is re-checked before printing, then update, sunset, or split it |
| `fix-ts-errors` | Fix TypeScript errors and loop the **workspace** type-check until it exits 0 — a file whose squiggles cleared is not green |
| `harden-plan` | Pre-code quality gate — grounds a written plan against the real codebase and runs 11 category checks before any code exists |
| `grill-me` | Interview-style stress-test of a plan, one decision at a time, against an enumerated list — no "grill complete" until every decision has an answer |
| `project-discovery` | Discovery interview before writing code on a new project — interrogate requirements and stack, then emit `CLAUDE.md`, `PATTERNS.md` and the `lib/` scaffolding |
| `design-director` | Senior creative-director direction — 7 modes (brief simplify, logo, layout, typography, color, critique, brand identity) |
| `browser-qa` | Drive a real browser through a UI flow with Playwright MCP — screenshot every step, check network and console, and account for every step with PASS or FAIL |
| `reuse-first` | Search-first discipline before writing any new utility, type, schema, component, hook, or constant — 3-layer search you must print, reuse ladder, fork smells |
| `backend-perf` | Performance checklist for backend endpoints and DB queries — walk every check and name a verdict on each; a check you did not name is a check you did not run |
| `systematic-debugging` | Four-phase root-cause loop for mid-debugging discipline — no fix without an understood cause, every phase ends on a checkable bar, bandaid budget zero |
| `verify-claims` | Gate inference-backed, decision-driving claims with a counter-hypothesis and paired evidence from their basis and user-facing acceptance boundary |
| `preflight-mutations` | Resolve exact targets, authority, dependencies, reversibility, confirmation, and read-back before changing shared state |
| `executing-tickets-with-subagents` | Execute a multi-sub-task GitHub ticket via subagents — one wave per task, ledger-tracked so a compaction can resume, follow-up triage, manual-QA handoff doc |
| `resolving-merge-conflicts` | Resolve an in-progress git conflict without a **silent drop** — every hunk from both sides placed as kept, superseded, or dropped before you commit |
| `git-commit` | Conventional commits from diff analysis — every file classified into exactly one commit; append-only, with a message-only mode |
| `openclaw-backup` | Verified restore point for an OpenClaw install — official archive, `VACUUM INTO` SQLite snapshots, a raw archive covering the session transcripts the official tool drops, checksum manifest, and a per-install `RESTORE.md`. Manual-only via `disable-model-invocation`, so its description stays out of context until you invoke it |

Several skills use progressive disclosure — `SKILL.md` holds the spine, and branch-specific material sits in `references/` (or `modes/` for `design-director`), loaded only when that branch fires. Load instructions use `${CLAUDE_SKILL_DIR}/` so they resolve against the skill directory rather than the user's repo.

## Bundled tooling (not slash commands)

| Folder | Purpose |
|---|---|
| `skills/coderabbit-config/` | `.coderabbit.yaml` template + persistent-learnings sidecar. Copy into a repo so CodeRabbit absorbs style + convention findings before `/review-pr` runs. See [`skills/coderabbit-config/README.md`](skills/coderabbit-config/README.md) for bootstrap instructions. |
| `tools/verify_skills.py` | Structural verifier across all skills — frontmatter, code fences, pointer form, severity-ladder consistency, dangling and orphan references, cross-skill duplication. Plus produce → validate → consume dataflow checks scoped to `review-pr` and `fix-pr-review`. Run `python3 tools/verify_skills.py ./skills`; exits non-zero on failure. |
| `tools/eval/run_verify_claims.py` | Fresh-session behavioral evaluator for `verify-claims` across code, external mutation, configuration, data, missing evidence, contradiction, and material reversal. Raw streams and final cards are saved under `.eval-results/`. |

## Usage

```
/done                # Run after every task
/parallel-review     # Review locally-changed code
/review-pr <pr-url>  # Review a GitHub PR (or several at once — batch mode)
/fix-pr-review       # Triage and apply CodeRabbit / review-pr findings
/audit-ticket <n>    # Audit a stale issue against current code — update or sunset it
/fix-ts-errors       # Fix TypeScript errors, loop until the workspace check is green
/browser-qa          # Drive a UI flow in a real browser
/harden-plan         # Stress-test a written plan before coding
/grill-me            # Interview-style plan/design refinement
/project-discovery   # Plan a new project
/design-director     # Design + branding direction
/reuse-first         # Search-first check before writing new utilities/types/components
/backend-perf        # Perf checklist for backend services and DB queries
/systematic-debugging  # Root-cause loop once you're inside a debugging session
/verify-claims         # Verify a consequential inference before relying on it
/preflight-mutations   # Prepare or block a shared-state mutation before execution
/executing-tickets-with-subagents  # Run a bundled ticket end-to-end via subagents
/resolving-merge-conflicts         # Resolve merge/rebase conflicts safely
/git-commit          # Conventional commit (or message-only)
/openclaw-backup     # Verified restore point for an OpenClaw install
```

## Reference

[`reference/CLAUDE.md`](reference/CLAUDE.md) — the global user-level `~/.claude/CLAUDE.md` these skills plug into. `reuse-first` and `backend-perf` were extracted from it into on-demand skills to keep the always-loaded file lean; the rest shows how the skills fit into a full rule setup.

## How `review-pr` + `coderabbit-config` work together

**CodeRabbit is the sieve; `/review-pr` is the critic-pass.** The sieve catches style, convention, and standard-pattern findings so the critic-pass only ever sees what needs judgement — intent grounding, codebase-wide reusability (Q6a), multi-round state, and anti-slop filtering on the merged findings.

Adopting `coderabbit-config` per-repo is what makes `/review-pr` runs tight. See [`skills/coderabbit-config/README.md`](skills/coderabbit-config/README.md) for the per-repo bootstrap.
