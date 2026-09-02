# Dispatch prompts

### Subagent 1: Claude reviewer (`general-purpose`)

Substitute `<SKILL_DIR>` throughout the prompt before it is used, before dispatching in
every mode, and equally before running it inline under `solo-main`, where main's own
working directory is the user's repo and a bare relative path misses in exactly the same
way.

`<SKILL_DIR>` is the absolute directory of the SKILL.md you are currently executing,
the `review-pr` directory this file sits in, resolved through any symlink. Derive it
from that location; never hardcode a path. The same skill installs at user scope
(`~/.claude/skills/review-pr`) and at project scope (`<repo>/.claude/skills/review-pr`),
so a hardcoded guess is wrong half the time and wrong silently.

Subagents inherit the user's repo as their working directory, so a bare `references/...`
path resolves against that repo and finds nothing. The load fails silently and the
subagent answers from memory instead. The same substitution applies to Subagent 3 and to
the Phase 3 verifiers.

#### Prompt substitutions

`<PROMPT_PREAMBLE>` and `<GROUND_TRUTH>` are each substituted into more than one prompt, so
this is their one definition. Every prompt that carries them names them by these tokens.
Substitute the block as written, with `<SKILL_DIR>` already resolved.

**`<PROMPT_PREAMBLE>`**: opens Subagent 1, Subagent 3 and V3, the three prompts that emit
findings. Each of them follows it with its own one-line statement of whether it closes on a
run-level verdict:

```text
## Where the reference files live
SKILL_DIR: <SKILL_DIR>
Your working directory is the user's repo, not the skill directory, so every
`<SKILL_DIR>/references/...` path in this prompt is absolute and must be used as written.
A bare `references/...` resolves against the repo and silently finds nothing.

## Output format, load this FIRST
Load `<SKILL_DIR>/references/finding-output-format.md` before you write anything. It holds
the per-finding field block, meaning `Rule-class`, `Enclosing-symbol`, `Class-sites`,
`Inverse risk` and the `class_completeness:` audit, plus the post-image line-number
convention and the run-level closing block. Emit every finding in exactly that shape; a finding in any other
shape is unparseable to the Phase 3 critic and is dropped.
```

**`<GROUND_TRUTH>`**. Opens Subagent 1 and Subagent 2:

```text
## Ground truth
Goal: <from Phase 1>
Expected touches: <from Phase 1>
Out of scope: <from Phase 1>
Prior findings already reported (raise one again only as a correction): <from Phase 1>
```

#### The prompt

Load `${CLAUDE_SKILL_DIR}/references/reviewer-prompt.md` at this dispatch. Every mode
reaches it, `solo-main` included, since that mode runs the same prompt body inline. It
holds the prompt, the anti-slop rules the reviewer works under, and the note on why the
finding shape is never restated inside it.

The context packet is part of the prompt, not commentary around it. Dispatch the whole block below. With only a URL, this subagent does not know what the PR is for or what earlier rounds closed. It re-finds settled issues and misses the rest.

Prompt:

```
Check for silent failures, swallowed errors, and inadequate error handling in the GitHub
PR at <url>. Fetch the diff yourself via `gh pr diff <url>`.

<GROUND_TRUTH>

## Already closed in earlier rounds, do not re-raise
<rule_class list from PRIOR_STATE.findings where status in {resolved, dismissed, wontfix}>
Re-raise one only when the diff shows the resolving code was reverted.
```
