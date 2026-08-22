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

Vercel, Stripe, Figma, Linear, Notion, Dub, Unkey, Resend and Clerk describe
nothing about what they do. A name takes its meaning from the product, never the
reverse, so describing the job is one option rather than the target. Judge an
abstract candidate on whether it can carry meaning once people use it, not on
whether it announces anything.

Two consequences for generation.

**Weight the lenses to the brief.** Compounder and Positioner both produce
describing names. When the brief wants a brandable mark rather than an
explanatory one, run Phonetic inventor wider and let the other two return fewer.

**Expect the availability pattern to invert.** Squatter bots brute-force
pronounceable strings, so abstract and invented names are the most contested part
of the namespace rather than the least. A 2026 run of 254 lookups for a developer
tool found zero free abstract names between 4 and 8 characters across `.com` and
`.dev`, while several descriptive compounds survived by pairing a common noun
with an unusual adjective: `meredoc`, `baredoc`, `inertpage`. A brandable short
`.com` is normally an aftermarket purchase. Say that early rather than after five
rounds of generation.

**Where the gaps actually are: onsets English does not use.** Bots generate
strings that look like English words, so consonant clusters absent from English
survive. In the same run, `zn` and `zv` openings produced six free five-letter
`.com` names (`zneft`, `znilo`, `zvist`, `znuvo`, `znaft`, `znisk`) after 240
lookups elsewhere had produced none. Switching language does not open a namespace
by itself: single dictionary words came back registered in Sanskrit, Hindi,
Japanese, Finnish, Turkish, Basque, Welsh, Latin, Greek, Polish, Malay, Swahili
and Icelandic, because investors run multilingual wordlists too. What survives is
a string no wordlist contains, so try `zn`, `zv`, `zl`, `kv`, `mj`, `tk`, `sv`
and foreign roots already carrying those clusters before concluding a namespace
is closed. The cost is a name people cannot spell from hearing it, so weigh that
against the radio test rather than treating availability as the win.

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
- fragment of a domain the user already owns + a new root;
- tone inversion, such as technical + warm or fast + safe;
- future-stretch substitution, such as `media` for `video`.

The owned-fragment operator compounds, so reach for it early when the user holds
any domain. It turns a domain they already have into the short-link half of a
pair at no cost, and it converts a fragment that means nothing alone into the
clipped form of a real name. In one 2026 run it produced the winner after roughly
400 lookups had produced no purchasable pair: an owned `fol.ink` plus the root
`slate` gave `folslate.com`, and `fol.ink` stopped being a compromise.

Keep provenance explicit: `VidsJar = vids from the category bank + jar from the
container bank`. When the user invents a combination, generate close, inverse,
and future-stretch siblings around it before returning to unrelated roots.

## Wart check

Run every surviving candidate through these before scoring. Each one eliminated a
finalist in a single 2026 run, and none is visible from the score alone.

- **Pejorative in the audience's own jargon.** `folsilo` failed: "siloed data" is
  a complaint in the vocabulary of the developers it was for, and the product
  shared documents.
- **Meaning in another major language the audience speaks.** `folmist` failed:
  `Mist` is German for manure, and `Mist!` is a mild expletive.
- **Spelling and pronunciation disagree in English.** `folquay` failed: `quay` is
  said "key", so it loses the radio test in both directions at once.
- **Collides with the user's other products, or with a brand a recorded decision
  deliberately separated this one from.** `folhex` failed: it read back to the
  parent brand that the new domain existed to isolate.

A wart disqualifies on its own. Do not average it away against a high score.

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

**Then show every name checked, grouped by the pattern it came from, with its
status.** Not only the finalists, and not only the survivors. The user is the
strongest remix engine in the loop: reading two hundred rejected names, they
routinely see a combination no lens generated, and a taken name still supplies
half of an available one. Trimming the list to keep the output tidy removes the
input that most often produces the winner, so hand over the whole pool and say
which parts of it are free.

Ask for one reaction containing:

1. whole names to keep;
2. atoms or sounds to reuse;
3. patterns to reject;
4. any combination the user wants to try.

The reaction is an input to the next naming round, not a vote tally.
