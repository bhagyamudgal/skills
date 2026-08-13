---
name: file-issue
description: File one GitHub issue an assignee can act on without asking what you meant. Use when reporting a bug, requesting work, or capturing a finding as a ticket. Breaking a plan into several linked tickets belongs to to-tickets instead.
---

# File an Issue

An issue is read by someone who was not there when the problem was found, often months later. Every bar below exists so that reader can act on it without coming back to ask what it meant.

## 1. Confirm this is one issue

One issue carries one observable problem and one acceptance condition.

Work that splits into several tickets with blocking edges between them belongs to `to-tickets`. A spec synthesised from the current conversation belongs to `to-spec`. Hand off rather than filing a container ticket that hides its real scope.

**Gate:** the scope is one problem with one acceptance condition, or the work is handed off by name.

## 2. Search before filing

```bash
gh issue list --search "<the symptom in your words>" --state all --limit 20
gh issue list --search "<the symptom in the reporter's words>" --state all --limit 20
```

Search twice with different vocabulary, because the existing ticket was filed by someone who described it differently. `--state all` matters: a closed near-match is either the thing to reopen or the context the new issue needs.

Resolve every near match before filing — duplicate, related, or genuinely new. A related one is linked with `Refs #N` and one line saying what is different about this one.

**Gate:** both searches ran and every near match has a resolution.

## 3. Compose the title

Prefix it under the issue-title rule in `CLAUDE.md`: conventional-commit type plus the module the work actually lives in, named the way the board reads it rather than the way the directory spells it.

The description clears the same bar as the title step in `file-pr` — name what is observed, never the mechanism you suspect, and no generic verb standing alone as the description.

**Tell:** a bug title names the wrong behaviour, not the suspected cause. `fix(auth): session drops on tab switch` survives being wrong about the cause; `fix(auth): cookie expiry miscalculated` becomes a lie the moment the cause turns out to be something else.

**Gate:** the title names an observation that stays true independent of the diagnosis.

## 4. Compose the body

Four parts, in this order, each one prose rather than a fragment:

- **What happens** — the observed behaviour, opening the body with no heading above it
- **How to see it** — exact steps, command, URL, or `file:line` evidence. Someone with repo access and nothing else has to reach the same observation from this alone.
- **What should happen instead** — stated separately from the observation, because the gap between them is the actual request
- **Done looks like** — one condition a reviewer can check. "Works properly" is not one.

Then only what carries content: `Refs #N` links, and the environment when it matters. Take the environment from evidence — the URL bar in a screenshot tells you whether this was production or dev — never from assumption.

Attach screenshots rather than describing them. A described screenshot loses everything the describer did not notice, and the person fixing this needs the image itself.

**Gate:** the four parts are present, and the reproduction stands on its own without the session that produced it.

## 5. Cold-read the result

Run the cold-read bars from `file-pr` against the composed title and body, then two more that only an issue has:

- **Reproduction** — someone with repo access and no other context reaches the observation
- **Acceptance** — the done condition is checkable by someone who did not write it

A bar you did not name is a bar you did not check.

**Gate:** every bar has a named result and none is failing.

## 6. File it

Creating an issue writes to shared state, so `preflight-mutations` owns the authorization and recovery for it. Then:

```bash
gh issue create --title "<title>" --body-file <path>
```

Set assignee, estimate, or priority only within the project-board ownership boundary in `CLAUDE.md`. Filing an issue does not make those fields yours to set.

Print the URL.

**Done:** the scope is one issue, both duplicate searches ran and resolved, the title names an observation that survives a wrong diagnosis, the body carries all four parts, every cold-read bar is named and clean, and the issue URL is printed.
