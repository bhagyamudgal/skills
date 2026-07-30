---
name: project-discovery
description: Discovery interview before writing code on a new project — interrogate
  requirements, stack, and conventions, then emit CLAUDE.md, PATTERNS.md and the
  project's lib/ scaffolding. Use when the user starts a new project, or when they
  seem unsure about a technical decision that will be expensive to reverse.
---

# Project Discovery

**Interrogate every answer.** "PostgreSQL" is the start of a question, not the end
of one — self-hosted or managed, what volume, what compliance, what's the backup
story. The second question is where the real constraint surfaces.

Every recommendation ships with its trade-off: what they gain, what they give up.
When a choice fights their constraints, say so and name the cheaper path.

## Discovery Categories

### 1. PROJECT OVERVIEW

| Question | Why It Matters |
|----------|----------------|
| What does this project do? Who is it for? | Frames all technical decisions |
| What problem are we solving? What's painful now? | Ensures we're solving real problems |
| How will we know if it's successful? | Defines done, prevents scope creep |
| What's the timeline? MVP vs full launch? | Determines build vs buy, complexity tolerance |
| Who's building this? Solo, small team, org? | Affects architecture, tooling choices |
| What's the budget for infrastructure/services? | Managed vs self-hosted decisions |

### 2-10. Every Other Layer

When the interview reaches a layer the user has not already decided — framework,
database, ORM, auth, API style, styling, hosting, integrations, testing — read
`references/stack-menu.md` and use that layer's option list and separating
questions. Do not name options from memory; the file exists so the trade-off you
quote is the one you'd quote next time.

## Conducting Discovery

### Opening

```
"Before we write any code, I want to understand what we're building and make sure we make good foundational decisions. This might take 15-30 minutes but will save hours later. Let's start with the big picture — what are we building and who is it for?"
```

### During Discovery

- Group related decisions: "So for the data layer, we're going with Postgres on Supabase with Drizzle ORM. That gives us..."
- Flag decisions that need more thought: "Let's come back to the auth flow once we understand the user types better"
- Challenge weak reasoning: "You said 'because everyone uses it' — is that the right reason for your specific case?"

### Closing Discovery

```
"Let me summarize what we've decided:

**Project**: [One sentence]
**Stack**: [Frontend] + [Backend] + [Database]
**Auth**: [Approach]
**Hosting**: [Where]
**Key patterns**: [2-3 important conventions]

**Features for MVP**:
1. [Feature]
2. [Feature]
...

Does this capture it? Anything we should revisit before we start building?"
```

## Output: What to Produce

1. Read `references/output-templates.md` and write `CLAUDE.md`, the folder
   skeleton, and the config files it lists.

2. The rule corpus is `references/coding-standards.md`. You need it once, when
   writing `PATTERNS.md` — read it then, copy across only the rules the chosen
   stack actually uses, and delete the rest. A rule for a library the project
   does not have is a rule the agent will misapply.

3. Copy all four files in `references/lib-files.md` into `lib/` verbatim.
   Verbatim — every downstream rule in `coding-standards.md` assumes these exact
   signatures.

**Done when:** `CLAUDE.md` names a decision for every category in
`references/stack-menu.md` — including categories decided as "not needed", with
the reason. `PATTERNS.md` exists and contains only rules the chosen stack uses.
All four files from `references/lib-files.md` are in `lib/`. An unnamed category
is an undiscovered one — go back and ask.
