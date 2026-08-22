# Naming lenses

Use this reference during atom extraction, independent generation, synthesis, and
the human remix round.

## Atom bank

Extract short reusable units rather than only complete names.

| Bucket | What it captures | Examples for a local video downloader |
|---|---|---|
| Category | What the product handles | video, vids, clip, media |
| Action | What the product does | fetch, save, pull, keep |
| Outcome | What the user gains | offline, owned, portable, ready |
| Object | A physical metaphor | jar, pocket, dock, nest |
| Place | A destination or refuge | harbor, home, vault, bay |
| Personality | Desired emotional signal | quick, calm, trusted, playful |
| Phonetic | Useful sounds or fragments | vid, clip, stash, zip |
| Expansion | Words that survive future scope | media, local, keep, fetch |

Tag each atom as `direct`, `suggestive`, `emotional`, `metaphorical`, or
`phonetic`. Record where it came from: product brief, agent candidate, user
reaction, or rejected name.

## Description is optional

Vercel, Stripe, Figma, Linear, Notion, Dub, Unkey, Resend and Clerk describe nothing about what they do. A name takes its meaning from the product, never the reverse, so describing the job is one option rather than the target. Judge an abstract candidate on whether it can carry meaning once people use it, not on whether it announces anything.

Two consequences for generation.

**Weight the lenses to the brief.** Compounder and Positioner both produce describing names. When the brief wants a brandable mark rather than an explanatory one, run Phonetic inventor wider and let the other two return fewer.

**Expect the availability pattern to invert.** Squatter bots brute-force pronounceable strings, so abstract and invented names are the most contested part of the namespace rather than the least. A 2026 run of 254 lookups for a developer tool found zero free abstract names between 4 and 8 characters across `.com` and `.dev`, while several descriptive compounds survived by pairing a common noun with an unusual adjective: `meredoc`, `baredoc`, `inertpage`. A brandable short `.com` is normally an aftermarket purchase. Say that early rather than after five rounds of generation.

## Independent lens contracts

Give every lens the naming brief and atom bank. Require 12 names with this shape:

```text
Name:
Pronunciation:
Atom recipe:
Product association:
Strongest weakness:
```

### Compounder

Combine one familiar atom with one surprising but understandable physical atom.
Favor category/action + container/place/tool patterns. Avoid joining two generic
software words.

Target behavior: `VidsJar` turns the obvious category atom `vids` into something
ownable by pairing it with the tactile container `jar`.

### Positioner

Name the benefit, identity, emotional outcome, or future boundary rather than the
mechanism. Include direct, suggestive, and stretch candidates; avoid empty premium
language.

### Phonetic inventor

Create pronounceable blends, clipped compounds, consonant hinges, and rhythmic
wildcards. Every candidate must pass both directions of the radio test: a person
can say it after reading it and spell it after hearing it.

## Remix operators

Apply several operators; do not produce eight suffix variants of one root.

- category + container;
- action + place;
- outcome + object;
- tactile object + digital job;
- singular/plural shift;
- verb/noun shift;
- clipped overlap between two atoms;
- prefix from one candidate + root from another;
- tone inversion, such as technical + warm or fast + safe;
- future-stretch substitution, such as `media` for `video`.

Keep provenance explicit: `VidsJar = vids from the category bank + jar from the
container bank`. When the user invents a combination, generate close, inverse,
and future-stretch siblings around it before returning to unrelated roots.

## Brand score (/70)

Score names before applying the domain gate.

| Dimension | Points | Test |
|---|---:|---|
| Strategic fit and stretch | 20 | Does not block the stated three-year boundary. An abstract name that describes nothing scores full marks; only a name that boxes the product in loses them |
| Memorability and distinction | 20 | Leaves a concrete image and is not a generic category label |
| Pronunciation and spelling | 20 | Passes the radio test in both directions |
| Tone fit | 10 | Matches the brief's desired signal and avoids forbidden associations |

Prefer 5–10 characters and 2 syllables, but use those as heuristics rather than
hard gates. Eliminate a name regardless of score when it has an unacceptable
meaning, an impossible pronunciation, or a direct contradiction with the brief.
Domain availability is the domain gate; do not award points for it.

## First-pass presentation

Show 12 candidates spanning all three lenses. For each, include pronunciation,
recipe, one-line fit, strongest weakness, score, and preliminary domain status.
Do not hide a creatively strong taken name before the remix turn; label it clearly
and preserve only its useful atoms.

Ask for one reaction containing:

1. whole names to keep;
2. atoms or sounds to reuse;
3. patterns to reject;
4. any combination the user wants to try.

The reaction is an input to the next naming round, not a vote tally.
