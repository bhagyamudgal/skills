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
npx skills update --global     # only user-level (~/.claude/skills/)
npx skills update -y           # skip scope prompt; auto-detect from cwd
```

If anything looks wedged, remove and re-add:

```bash
npx skills remove bhagyamudgal/skills -s '*' -y
npx skills add bhagyamudgal/skills
```

## Skills (slash commands)

| Skill | Description |
|-------|-------------|
| `done` | MANDATORY post-task verification — type-check, parallel code review, code simplification |
| `parallel-review` | Run code-review + CodeRabbit review in parallel on locally-changed code |
| `review-pr` | Deep anti-slop review of a GitHub PR with critic-pass filtering, persistent multi-round state, and rolling-review posting |
| `fix-pr-review` | Triage and fix CodeRabbit / `review-pr` findings, then reply + resolve PR conversations |
| `fix-ts-errors` | Autonomous TypeScript error detection and fixing loop |
| `harden-plan` | Pre-code quality gate — validates plans against 11 category checks before implementation |
| `grill-me` | Interview-style stress-test of a plan or design, one decision at a time, until aligned |
| `project-discovery` | Deep project discovery and architecture planning for new projects |
| `design-director` | Senior creative-director voice — 7 modes (brief simplify, logo, layout, typography, color, critique, brand identity) |
| `qa` | Smart browser testing with Playwright automation |
| `reuse-first` | Search-first discipline before writing any new utility, type, schema, component, hook, or constant — 3-layer search, reuse hierarchy, duplicate smells |
| `backend-perf` | Performance checklist for backend services and DB queries — parallel async, N+1 nuance, index coverage, EXPLAIN-evidence for rewrites |

## Bundled tooling (not slash commands)

| Folder | Purpose |
|---|---|
| `skills/coderabbit-config/` | `.coderabbit.yaml` template + persistent-learnings sidecar. Copy into a repo so CodeRabbit absorbs style + convention findings before `/review-pr` runs. See [`skills/coderabbit-config/README.md`](skills/coderabbit-config/README.md) for bootstrap instructions. |

## Usage

```
/done                # Run after every task
/parallel-review     # Review locally-changed code
/review-pr <pr-url>  # Review a GitHub PR
/fix-pr-review       # Triage and apply CodeRabbit / review-pr findings
/fix-ts-errors       # Fix TypeScript errors
/qa                  # Run browser tests
/harden-plan         # Stress-test a written plan before coding
/grill-me            # Interview-style plan/design refinement
/project-discovery   # Plan a new project
/design-director     # Design + branding direction
/reuse-first         # Search-first check before writing new utilities/types/components
/backend-perf        # Perf checklist for backend services and DB queries
```

## Reference

[`reference/CLAUDE.md`](reference/CLAUDE.md) — the global user-level `~/.claude/CLAUDE.md` these skills plug into. `reuse-first` and `backend-perf` were extracted from it into on-demand skills to keep the always-loaded file lean; the rest shows how the skills fit into a full rule setup.

## How `review-pr` + `coderabbit-config` work together

`/review-pr` is structured as two layers:

- **CodeRabbit** (configured via `coderabbit-config/coderabbit.yaml.template`) handles style, convention, and standard-pattern findings — `any` usage, `!.` non-null assertions, magic numbers, missing `Promise.all`, N+1 queries, etc.
- **Claude reviewer** (the `/review-pr` skill itself) handles intent grounding, codebase-wide reusability checks (Q6a), multi-round state tracking, and anti-slop critic filtering on the merged findings.

Adopting `coderabbit-config` per-repo is what makes `/review-pr` runs tight — CodeRabbit catches routine issues before the skill loads, so the reviewer subagent can focus on what only deep semantic + codebase-wide work can do. See [`skills/coderabbit-config/README.md`](skills/coderabbit-config/README.md) for the per-repo bootstrap.
