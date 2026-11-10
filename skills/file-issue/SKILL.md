---
name: file-issue
description: File one GitHub issue an assignee can act on unaided. Use when reporting a bug, requesting work, or capturing a finding as a ticket.
---

# File an issue

The reader of an issue was not there when the problem surfaced, often months ago. Every bar below lets that reader act without coming back to ask what it meant.

## 1. Confirm this is one issue

One issue carries one observable problem and one acceptance condition.

Hand work that splits into several tickets with blocking edges to `to-tickets`, and a spec built from the current conversation to `to-spec`. Never file a container ticket that hides its real scope.

File an issue nobody asked for without asking only when it is Critical, Serious, or an important user-facing problem, one a user of the shipped product can hit. For anything else, ask the user first. An unattended run files none of the ask-first issues and lists each in its report. A filing that a calling skill's documented step authorizes counts as requested, for example `review-pr`'s `github-posting.md` step 8c or `executing-tickets-with-subagents` Phase 3 endgame step 5, so neither the ask-first rule nor the unattended rule applies to it.

**Gate.** One problem with one acceptance condition, or a handoff by name, and an unrequested issue clears the filing bar above.

## 2. Search before filing

```bash
gh issue list --repo "$repository" --search "<the symptom in your words>" --state all --limit 20
gh issue list --repo "$repository" --search "<the symptom in the reporter's words>" --state all --limit 20
```

Search twice with different vocabulary, because whoever filed the existing ticket described it differently. Keep `--state all`. A closed near-match is either the thing to reopen or context the new issue needs.

Resolve every near match as duplicate, related, or new. Link a related one with `Refs #N` and one line saying how this one differs.

**Gate.** Both searches ran and every near match has a resolution.

## 3. Compose the title

Prefix the title under the issue-title rule in `CLAUDE.md`: conventional-commit type plus the module the work lives in, named the way the board reads it, not the way the directory spells it.

The description clears the same bar as the title step in `file-pr`. Name what you observe, never the mechanism you suspect, and never a generic verb alone.

A bug title names the wrong behaviour, not the suspected cause. `fix(auth): session drops on tab switch` survives a wrong guess about the cause. `fix(auth): cookie expiry miscalculated` becomes a lie the moment the cause turns out to be something else.

**Gate.** The title names an observation that stays true whatever the diagnosis.

## 4. Compose the body

Four parts, in this order, each in prose rather than fragments:

- **What happens.** The observed behaviour, opening the body with no heading above it.
- **How to see it.** Exact steps, command, URL, or `file:line` evidence. Someone with repo access and nothing else reaches the same observation from this alone.
- **What should happen instead.** Kept apart from the observation, because the gap between them is the request.
- **Done looks like.** One condition a reviewer can check. "Works properly" is not one.

Then add only what carries content: `Refs #N` links, and the environment when it matters. Take the environment from evidence, such as the URL bar in a screenshot showing production or dev. Never assume it.

Attach screenshots instead of describing them. A description loses everything the describer did not notice, and whoever fixes this needs the image.

**Gate.** All four parts are present and the reproduction works without the session that produced it.

## 5. Cold-read the result

Run the cold-read bars from `file-pr` against the composed title and body, plus two that only an issue has:

- **Reproduction.** Someone with repo access and no other context reaches the observation.
- **Acceptance.** Someone who did not write the done condition can check it.

**Gate.** Every bar has a named result and none fails. A bar you did not name is a bar you did not check.

## 6. File it

Render the final body to a file and record its SHA-256 digest. Resolve the repository's stable identity and current duplicate-search results, then invoke `preflight-mutations` with the exact repository, title, body path and digest, create options including `--label ai-created`, ownership boundary, and authoritative read-back query. A changed title, option, label, body path, digest, repository, or duplicate result invalidates the card.

Make sure the `ai-created` provenance label exists before creating. It marks every issue this skill files, so agent-filed issues stay distinguishable from human-filed ones. When it is absent, raise a separate label-creation card through `preflight-mutations` naming the repository. Look the label up by exact name, never through a capped listing, tolerate only the already-exists race on create, and prove the label reads back:

```bash
if ! gh api "repos/$repository/labels/ai-created" >/dev/null 2>&1; then
  create_out=$(gh label create ai-created --repo "$repository" --color "A2EEEF" --description "Created by an AI agent" 2>&1) || printf '%s\n' "$create_out" | grep -qiE "already.?exists"
fi
gh api "repos/$repository/labels/ai-created" --jq .name | grep -Fqx "ai-created"
```

Creating an issue writes to shared state, so continue only on a current `ready` result. Pass the title as one argument and the frozen body by file, always with the provenance label:

```bash
gh issue create --repo "$repository" --title "$title" --body-file "$body_path" --label "ai-created"
gh issue view <issue-url> --repo "$repository" --json number,title,body,state,author,assignees,labels,url
```

Set assignee, estimate, or priority only within the project-board ownership boundary in `CLAUDE.md`. Filing an issue does not make those fields yours. Never drop `ai-created` to set another label. Triage labels go on beside it.

Require one created URL, then compare the fetched repository, title, body, labels, metadata, and URL with the approved payload. Require `ai-created` in the fetched labels. When the command result is missing or ambiguous, search the target repository for exact-title candidates and compare their bodies and metadata. Mark the attempt `reconcile-required` and do not retry until that authoritative search proves whether the issue exists.

Print the URL only after read-back identifies one matching issue.

The run is done when every section gate above passes and authoritative read-back identifies the printed issue URL carrying the `ai-created` label, or the attempt stays `reconcile-required` without retry.
