# Skills

Custom Claude Code skills for development workflows — code review, TypeScript fixes, QA automation, and PR reviews.

## Install

```bash
# Install all skills
npx skills add bhagyamudgal/skills

# Install a specific skill
npx skills add bhagyamudgal/skills@done

# List available skills
npx skills add bhagyamudgal/skills -l
```

## Skills

| Skill | Description |
|-------|-------------|
| `done` | Post-task verification pipeline — type-check, parallel code review, and code simplification |
| `parallel-review` | Run code review + CodeRabbit review in parallel on changed code |
| `review-pr` | Deep anti-slop review of a GitHub PR with critic-pass filtering |
| `fix-pr-review` | Triage and fix CodeRabbit/review-pr findings, then reply + resolve PR conversations |
| `fix-ts-errors` | Autonomous TypeScript error detection and fixing loop |
| `harden-plan` | Pre-code quality gate — validates plans against 11 category checks before implementation |
| `forge-plan` | Full idea-to-implementation pipeline (brainstorm → grill → harden → execute) |
| `project-discovery` | Deep project discovery and architecture planning for new projects |
| `qa` | Smart browser testing with Playwright automation |

## Usage

Skills are invoked as slash commands in Claude Code:

```
/done                  # Run after every task
/parallel-review       # Review changed code
/review-pr 123         # Review a GitHub PR
/fix-ts-errors         # Fix TypeScript errors
/qa                    # Run browser tests
/forge-plan            # Full development pipeline
```
