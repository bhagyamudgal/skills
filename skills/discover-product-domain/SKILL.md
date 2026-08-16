---
name: discover-product-domain
description: Generate, remix, and rank product or app names, then verify their exact standard-price .com domains. Use when naming an app or product, remixing name fragments or an existing name, or checking a name shortlist.
---

# Discover Product Domains

Turn a product idea into memorable names whose exact `.com` domains are
confirmed at a registrar. Treat human combinations such as `Vids` + `Jar` as a
core discovery mechanism, not an afterthought.

## Mode

Use **guided mode** by default. Extract known facts first, then ask one unresolved
high-impact question at a time with 2–4 options and the recommended choice first.
Use **rapid mode** only when the user explicitly asks for a quick, autonomous, or
single-pass result; apply the defaults below and skip the human remix turn.

Registrar and account interactions are read-only. Search and verify domains, but
stop before sign-in, cart, offer, purchase, registration, handle creation, or any
other external mutation. A local Markdown report is allowed only when requested.

## Entry route

Choose the shortest route that preserves work the user already supplied:

- **Greenfield:** run the full funnel from step 1.
- **Supplied shortlist:** capture or default the brief, then skip step 3. Score
  and registry-filter every supplied name in step 4. If the user asked only for
  verification or ranking, proceed directly to registrar confirmation and return
  the ranked survivors; do not force an atom bank, new-name generation, or a remix
  turn. If the user also requests alternatives, build the step 2 atom bank from the
  supplied names and the brief, treat the supplied set as the human reaction, and
  continue to step 5 after scoring and filtering it.
- **Remix or refinement:** treat the supplied names, fragments, or single name as
  the human reaction. Build an atom bank from them and the brief, then enter at
  step 5. The supplied material satisfies the guided-mode remix requirement.

Do not replace, silently expand, or ignore a supplied candidate set. Generate
beyond it only when the request asks for alternatives or the user approves
loosening an insufficient shortlist.

Before any route scores, remixes, or checks a name, read both
`${CLAUDE_SKILL_DIR}/references/naming-lenses.md` and
`${CLAUDE_SKILL_DIR}/references/domain-verification.md` completely.

## Funnel

### 1. Lock the naming brief

Capture these fields from the conversation before asking anything:

- what is being named and its one-sentence job;
- primary audience and market language;
- core promise and desired emotional signal;
- three-year expansion boundary;
- desired and forbidden tones, words, sounds, and associations.

Default unresolved preferences to warm, clear, credible, globally pronounceable,
5–10 characters, 2 syllables where natural, and no hyphens or digits. In guided
mode, ask only when a different answer would materially change the candidate set.

**Complete when:** every field is answered or carries an explicit default.

### 2. Build the atom bank

Extract at least 12 distinct **atoms** across at least four semantic buckets from
`naming-lenses.md`. Mark each atom's source and type so later remixes preserve
their provenance.

**Complete when:** the atom bank has enough direct, suggestive, metaphorical,
emotional, and phonetic material for all three naming lenses.

### 3. Generate independently

Dispatch three naming agents in parallel when subagents are available. Read and
use the complete lens contracts in `naming-lenses.md`:

1. **Compounder**
2. **Positioner**
3. **Phonetic inventor**

Give each agent the same brief and atom bank, but none of the other agents'
candidates. Embed that agent's complete lens rules and the required output shape
from `naming-lenses.md` in its task; do not assume a subagent can resolve this
skill's relative paths. Each returns 12 names. When subagents are unavailable,
run the three lenses sequentially and keep their pools separate until synthesis.

**Complete when:** 36 raw names exist, 12 from each independent lens.

### 4. Synthesize or assess

For a greenfield route, deduplicate the pool, apply the remix operators and scoring
rubric in `naming-lenses.md`, and select 12 names spanning all three lenses. For a
supplied shortlist, preserve and score every supplied candidate without demanding
12 names or artificial lens coverage. Preserve strong atoms from rejected names;
a taken compound can still contain half of the winner.

Bulk-filter the current candidate set's canonical `.com` domains through the
registry evidence stage and account for every lookup with the status vocabulary
in `domain-verification.md`.

In guided greenfield mode, present the first pass and collect the one structured
reaction defined in `naming-lenses.md`. In rapid mode, create an autonomous
reaction: retain the four strongest atoms or patterns, reject weaknesses shared by
the bottom candidates, and record that no user preference was inferred.

**Complete when:** a greenfield user supplied a remix reaction; rapid mode recorded
its autonomous reaction; a shortlist-with-alternatives preserved the supplied set
as its reaction; or a verification-only shortlist has a registry status for every
supplied name.

### 5. Produce eight remixes

Treat every user-created combination as a first-class seed. Send the reaction to
the original lens owners as follow-up tasks when possible, embedding the relevant
remix operators and output contract in each task. Otherwise apply the operators
locally. Produce eight new names that cross favored atoms while avoiding rejected
patterns. Score the original supplied seeds and the eight remixes together, then
bulk-filter every canonical `.com` not already checked.

**Complete when:** eight non-cosmetic remixes have a recorded registry status.

### 6. Control expansion

A **viable candidate** has `candidate_available_rdap`; this permits registrar
confirmation but does not prove the domain can be bought.

Use these transitions; do not wait in step 6 for evidence that only step 7 can
produce:

- **Invalid supplied spelling:** request the exact `.com` spelling and stop with
  **Input blocked** until the user resolves it. Record and exclude invalid generated
  candidates without treating them as evidence failures.
- **Unknown evidence:** retry once using the backoff in `domain-verification.md`.
  Keep a nonessential generated unknown recorded and exclude it when enough other
  candidates can meet the active gate. If an unknown belongs to a supplied
  shortlist or prevents the active gate, stop with **Evidence blocked**; do not
  spend naming rounds during an evidence outage.
- **Unchecked viable candidates exist:** proceed to step 7.
- **Fewer than three finalists and no unchecked viable candidate:** if the active
  route permits generation and fewer than two expansion rounds have run, dispatch
  the three lenses with failed roots, registrar rejection reasons, favored atoms,
  and length constraints. Embed each lens's complete rules and output contract as
  in step 3. Deduplicate and score the new pool, select its strongest new names,
  registry-filter them, then apply these transitions again.
- **Two expansion rounds exhausted:** ask which naming constraint to loosen—atom
  vocabulary, tone, maximum length, or compound complexity. Do not weaken the
  exact standard-price `.com` gate. An answer resets the expansion counter once;
  a declined or fruitless loosening stops with **Generation shortfall**.
- **Verification-only supplied shortlist:** never expand; proceed until every
  viable supplied candidate has registrar evidence, then report the survivors.

Keep each lens independent during generation.

### 7. Confirm at the registrar

Follow the confirmation stage in `domain-verification.md`. For a generation route,
confirm enough viable candidates to produce three exact `.com` finalists. For a
verification-only shortlist, confirm every viable supplied candidate. Record the
evidence fields required by that reference.

Exclude premium, aftermarket, reserved, taken, and unknown domains from the final
three. Recheck a chosen name immediately before the user acts because availability
is never reserved by a search.

If fewer than three finalists survive and the active route permits new names,
return to step 6. For a verification-only supplied shortlist, report the shortfall
without inventing replacements.

**Complete when:** a generation route has three registrar-confirmed finalists or a
step 6 **Generation shortfall**; or every supplied domain in a verification-only
shortlist has a terminal status:
`registered`, `registrar_confirmed_available`, or `premium_or_reserved`. A
`candidate_available_rdap` remains non-terminal until registrar confirmation.
Identify the strongest survivor when one exists. Otherwise follow the step 6
transition that matches the current state.

### 8. Recommend

For a generation route, return exactly three finalists unless the user asks for
more; when a **Generation shortfall** ended the funnel, return every survivor and
report the shortfall instead of inventing replacements. For a verification-only
shortlist, rank the registrar-confirmed survivors without inventing names to fill
a quota. For each returned name, include:

- spelling and pronunciation;
- why it fits and its strongest downside;
- brand score out of 70;
- registrar-confirmed domain evidence and prices.

For generation, alternatives, remix, and refinement routes, also include the atom
recipe, lens or user provenance, and two nearby remix directions. Verification-only
results omit those generation artifacts.

Name a winner when at least one name survives. When at least two survive, also
name a runner-up and state the deciding trade-off in one sentence. When none
survive, report the shortfall without recommending a name. Keep user preference
separate from the numeric brand score. Warn that the workflow did not perform
trademark clearance, social-handle verification, or legal review.

Save a durable report only when requested. Derive a snake_case slug from the
free-text idea label in three ordered steps: lowercase the label, replace
non-alphanumeric runs with `_`, then strip leading and trailing `_` characters.
Require the whole slug to match the non-empty basename pattern
`^[a-z0-9]+(?:_[a-z0-9]+)*$`. Never accept a caller-supplied output path;
reject a supplied filename or slug when it is absolute or contains a path
separator or `.`/`..` path segment. Resolve
`docs/<slug>_domain_discovery.md` against the repository's resolved `docs/`
directory and write only when the result's parent is that directory. Include the
brief, entry route, supplied or generated candidate set, rejected domains,
finalists or survivors, evidence timestamps, a winner when one exists, and a
runner-up only when at least two names survive. Include route-produced artifacts:

- **Greenfield:** atom bank, first 12, user or autonomous reaction, and remixes.
- **Shortlist with alternatives:** supplied shortlist, atom bank, its reaction,
  and remixes.
- **Remix or refinement:** supplied seeds, atom bank, reaction, and remixes.
- **Verification-only shortlist:** supplied shortlist; omit or mark the first 12,
  reaction, and remixes as not applicable.

## Terminal states

- **Shortlist complete:** three registrar-confirmed finalists and a recommendation.
- **Generation shortfall:** fewer than three registrar-confirmed finalists survive
  after both expansion rounds and a declined or exhausted loosening; report every
  survivor with its evidence and name the shortfall.
- **Supplied shortlist verified:** every supplied name is accounted for and the
  strongest registrar-confirmed survivor is identified, if one exists.
- **Evidence blocked:** required domain evidence remains `unknown` after the
  permitted retry; name the affected domains and failed evidence boundary.
- **Input blocked:** a supplied name has no unambiguous valid `.com` spelling;
  request that exact spelling before continuing verification.
- **Decision complete:** the user chooses a winner.
- **Verification complete:** the chosen domain is rechecked at the registrar.
- **Acquisition complete:** only a separately authorized, successful registration
  can establish this; this skill never claims it.

## Completion gate

Finish only when every domain actually queried is accounted for. Greenfield guided
mode includes one human remix round; remix/refinement routes preserve the supplied
human remix; rapid mode records that the human remix was intentionally skipped.
A generation route requires three registrar-confirmed finalists with current
registrar evidence and an explicit winner-versus-runner-up trade-off, or a
reported generation shortfall that names every survivor with its evidence. A
verification-only shortlist route requires every supplied domain to be
`registered`, `registrar_confirmed_available`, or `premium_or_reserved`;
`candidate_available_rdap` never satisfies completion. Identify the strongest
survivor when one exists, or report the shortfall without a recommendation when
none survive. An `unknown` returns **Evidence blocked** only when it belongs to a
supplied shortlist or prevents the active gate, and an `invalid_candidate` returns
**Input blocked** only for a supplied name; a generated `unknown` or
`invalid_candidate` that was recorded and excluded does not block completion.
