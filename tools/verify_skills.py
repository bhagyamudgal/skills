#!/usr/bin/env python3
"""Structural verifier for the skills repo.

Exists because a naive fence COUNT gave a false pass while the prompt template
was actually broken: an inner ``` closed the outer fence, silently ejecting 54
lines of output-format spec out of the prompt. Count parity is not nesting.

Two tiers:
  * repo-wide — every directory under ROOT that holds a SKILL.md. File-agnostic
    structure: fences, frontmatter, pointer form, reference existence, the
    shared severity ladder, cross-skill duplication, the always-loaded context
    budget.
  * pair-only — the review-pr <-> fix-pr-review field contracts. Those field
    chains exist in no other skill; running them repo-wide is pure noise.

Plus one check on ROOT's sibling `reference/CLAUDE.md`, which claims to mirror a
file living outside the repo entirely.

A directory without a SKILL.md is bundled tooling, not a skill, and is skipped.
"""
import difflib, hashlib, re, sys, pathlib

ROOT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 \
    else pathlib.Path.home() / ".agents/skills"
RP = ROOT / "review-pr/SKILL.md"
FP = ROOT / "fix-pr-review/SKILL.md"
SCHEMA = ROOT / "review-pr/references/finding-state-schema.md"

fails, warns, notes = [], [], []


def rel(p):
    try:
        return str(pathlib.Path(p).relative_to(ROOT))
    except ValueError:
        return str(p)


def fail(t, m): fails.append((t, m))
def warn(t, m): warns.append((t, m))
def note(t, m): notes.append((t, m))


def read(p):
    return p.read_text(encoding="utf-8").split("\n") if p.exists() else None


# --- skill discovery -------------------------------------------------------

SKILLS = sorted(
    (p for p in ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").exists()),
    key=lambda p: p.name,
) if ROOT.exists() else []

SKILL_MD = {s.name: sorted(s.rglob("*.md")) for s in SKILLS}
EVERY_MD = [p for files in SKILL_MD.values() for p in files]


def skill_dir_of(path):
    return ROOT / rel(path).split("/")[0]


def check_fences(path, lines):
    """Track fence depth by marker length. An inner fence must be LONGER than
    the outer one, else it closes it (CommonMark)."""
    stack = []
    for i, l in enumerate(lines, 1):
        m = re.match(r"^(\s*)(`{3,})(.*)$", l)
        if not m:
            continue
        indent, ticks, info = m.group(1), m.group(2), m.group(3).strip()
        if stack and len(ticks) >= len(stack[-1][1]) and not info:
            stack.pop()                      # valid close
        elif info or not stack:
            stack.append((i, ticks))         # open
        else:
            stack.pop()
    if stack:
        fail(rel(path), f"unclosed fence opened at line {stack[0][0]}")


def check_nested_prompt(path, lines):
    """A fenced block that CONTAINS another fence must open with strictly more
    backticks than the inner one. This is the check that a naive parity count
    misses: an equal-length inner fence closes the outer block instead of
    nesting, silently ejecting everything after it."""
    open_at, open_len = None, 0
    for i, l in enumerate(lines, 1):
        m = re.match(r"^(\s*)(`{3,})(.*)$", l)
        if not m:
            continue
        ticks, info = m.group(2), m.group(3).strip()
        if open_at is None:
            open_at, open_len = i, len(ticks)
            inner = 0
        elif len(ticks) >= open_len and not info:
            if inner and open_len <= 3:
                fail(rel(path),
                     f"fence at {open_at} uses {open_len} backticks and contains "
                     f"{inner} inner fence(s). The first inner fence CLOSES it. "
                     f"Use {'`' * (open_len + 1)} for the outer fence.")
            open_at = None
        else:
            inner += 1


# --- frontmatter -----------------------------------------------------------

KNOWN_FRONTMATTER_KEYS = {
    "name", "description", "disable-model-invocation", "allowed-tools",
}


def _parse_frontmatter(lines):
    """Return (keys_in_order, values) or None if there is no frontmatter block.
    Continuation lines of a folded scalar are indented, so only column-0
    `key:` lines start a new key."""
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
    if end is None:
        return None
    keys, values, current = [], {}, None
    for l in lines[1:end]:
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s?(.*)$", l)
        if m:
            current = m.group(1)
            keys.append(current)
            values[current] = m.group(2).strip()
        elif current and l.strip():
            values[current] = (values[current] + " " + l.strip()).strip()
    return keys, values


def check_frontmatter():
    """The harness reads `name` to route the skill and `description` to decide
    whether to fire it. A name that disagrees with the directory routes to
    nothing. Unknown keys are ignored by the harness — informational only."""
    for skill in SKILLS:
        path = skill / "SKILL.md"
        parsed = _parse_frontmatter(read(path))
        if parsed is None:
            fail(skill.name, "SKILL.md has no parseable `---` frontmatter block")
            continue
        keys, values = parsed
        name = values.get("name", "").strip().strip("\"'")
        if not name:
            fail(skill.name, "frontmatter has no `name:`")
        elif name != skill.name:
            fail(skill.name, f"frontmatter `name: {name}` does not match its "
                             f"directory `{skill.name}`. The harness routes on "
                             f"the name, so this skill is unreachable")
        if not values.get("description", "").strip().strip("\"'"):
            fail(skill.name, "frontmatter has no non-empty `description:`. The "
                             "harness decides when to fire the skill from it")
        for key in keys:
            if key not in KNOWN_FRONTMATTER_KEYS:
                warn(skill.name, f"frontmatter key `{key}` is not one of "
                                 f"{sorted(KNOWN_FRONTMATTER_KEYS)}. The harness "
                                 f"ignores it")


# --- always-loaded context budget (repo-wide, WARN) ------------------------

# 360 is the repo's real ceiling today (harden-plan, 358). discover-product-domain
# landed at 506 — 41% past the previous worst — and nothing caught it at review.
MAX_DESCRIPTION_CHARS = 360

# Set from the repo's own distribution: two skills sit past 10 KB with the
# whole body in SKILL.md; every other skill that size splits into references/.
MAX_SKILL_MD_BYTES = 10_000


def _frontmatter_values(skill):
    parsed = _parse_frontmatter(read(skill / "SKILL.md"))
    return parsed[1] if parsed else {}


def _description(values):
    return values.get("description", "").strip().strip("\"'")


def _is_model_invoked(values):
    flag = values.get("disable-model-invocation", "").strip().strip("\"'")
    return flag.lower() != "true"


def description_budget():
    """(chars always in context, model-invoked skills, opted-out skills)."""
    total, invoked, opted_out = 0, 0, 0
    for skill in SKILLS:
        values = _frontmatter_values(skill)
        if _is_model_invoked(values):
            total += len(_description(values))
            invoked += 1
        else:
            opted_out += 1
    return total, invoked, opted_out


def check_description_budget():
    """A description is loaded on every turn of every session whether or not the
    skill fires, which makes it the most expensive line in the repo. A skill
    setting `disable-model-invocation: true` is never matched against, costs
    nothing, and is excluded from the budget entirely."""
    for skill in SKILLS:
        values = _frontmatter_values(skill)
        if not _is_model_invoked(values):
            continue
        size = len(_description(values))
        if size <= MAX_DESCRIPTION_CHARS:
            continue
        warn(skill.name,
             f"description is {size} chars, {size - MAX_DESCRIPTION_CHARS} over the "
             f"{MAX_DESCRIPTION_CHARS}-char budget. Every session pays for it on "
             f"every turn, fired or not. Cut it back to the trigger, or set "
             f"`disable-model-invocation: true` and make it user-invoked")


# A skill name is matched whole, treating `-` as a word character: `review-pr`
# must not hit inside `fix-pr-review`, and `simplify` must not hit `simplified`.
def _whole_name(name):
    return re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")


REFERENCE_DIR = ROOT.parent / "reference"


def _inbound_search_corpus():
    """Everything another skill could reach a skill from. The repo README lists
    every skill by name, so counting it would make the check vacuous — the
    question is whether anything ROUTES to the skill, not whether it is
    catalogued."""
    paths = [p for p in sorted(ROOT.rglob("*")) if p.is_file()]
    if REFERENCE_DIR.is_dir():
        paths += [p for p in sorted(REFERENCE_DIR.rglob("*")) if p.is_file()]
    corpus = []
    for path in paths:
        try:
            corpus.append((path, path.read_text(encoding="utf-8")))
        except (UnicodeDecodeError, OSError):
            continue
    return corpus


def check_orphan_model_invocation():
    """Model-invocation buys two kinds of reach — the agent recognising the
    situation itself, and another skill routing to it — and a reference search
    can only rule out the second. So this reports the fact and leaves the
    verdict to a human: resolving-merge-conflicts has no caller anywhere and
    must stay model-invoked, because the agent reaches it off `CONFLICT
    (content)` with nobody naming it.

    Narrowing it by description shape was tried and abandoned. `Use when the
    user ...` opens project-discovery, which fires autonomously when the user
    "seems unsure". Matching `only` scored 2/2 on the tree of the day and is an
    accident: on the since-removed calibrate-board-mutations it matched inside
    `read-only`, which is about data access, not invocation. A broad gate a
    human triages beats a heuristic that demotes a skill silently."""
    corpus = _inbound_search_corpus()
    for skill in SKILLS:
        values = _frontmatter_values(skill)
        if not _is_model_invoked(values) or not _description(values):
            continue
        pattern, own = _whole_name(skill.name), f"{skill.name}/"
        if any(pattern.search(text) for path, text in corpus
               if not rel(path).startswith(own)):
            continue
        warn(skill.name,
             f"model-invoked with no inbound reference from {ROOT.name}/ or "
             f"{REFERENCE_DIR.name}/. No other skill routes to it, so the "
             f"always-loaded description is buying autonomous recognition and "
             f"nothing else. Keep it if the agent must fire this off a situation "
             f"the user will not name; if it only ever fires when the user asks "
             f"for it, set `disable-model-invocation: true`")


def check_progressive_disclosure():
    """Past ~10 KB a SKILL.md carries detail most invocations never read, and
    all of it loads the moment the skill fires. references/ is how the rest of
    the repo separates the trigger path from the depth behind it."""
    for skill in SKILLS:
        size = (skill / "SKILL.md").stat().st_size
        if size <= MAX_SKILL_MD_BYTES or (skill / "references").is_dir():
            continue
        warn(skill.name,
             f"SKILL.md is {size:,} bytes with no references/. Every invocation "
             f"loads all of it. Move the depth behind "
             f"${{CLAUDE_SKILL_DIR}}/references/ and point at it from SKILL.md")


# --- severity ladder (repo-wide) -------------------------------------------

CANONICAL_LADDER = ["Critical", "Serious", "Moderate", "Minor"]
FOREIGN_RUNGS = ["Important", "Major", "Blocker"]

# A line quoting another tool's taxonomy legitimately names rungs we do not use.
# CodeRabbit's ladder is Critical|Major|Minor|Refactor|Nitpick and fix-pr-review
# has to document the mapping.
FOREIGN_TAXONOMY_MARKERS = ("CodeRabbit", "Nitpick", "Refactor suggestion")

# `Critical / Important`, `Critical | Major`, `Critical and Serious` — a rung
# word sitting next to another rung word across a list separator is a ladder,
# not prose that happens to contain the word "critical".
_LADDER_SEP = r"[\s`*]*(?:[/|>,]|\band\b|\bor\b)[\s`*]*"
_CANON_ALT = "|".join(CANONICAL_LADDER)

# A gate is a sentence that decides whether work may close. Kept to phrases that
# only ever appear in a closing condition — "before merging" was tried and
# matched the body text of a finding message, which is prose, not a gate.
GATE_MARKERS = (
    "zero open", "no open", "no remaining", "not complete", "closes at",
    "blocks the merge",
)


def check_severity_ladder_consistency():
    """The repo ladder is Critical > Serious > Moderate > Minor. A skill that
    invents a rung, or gates on a subset with a hole in it, silently passes
    every finding that lands on the unnamed rung — which is exactly how
    `Serious` findings sailed through executing-tickets-with-subagents while
    its callee parallel-review was emitting them."""
    for path in EVERY_MD:
        for i, l in enumerate(read(path) or [], 1):
            if any(marker in l for marker in FOREIGN_TAXONOMY_MARKERS):
                continue
            for rung in FOREIGN_RUNGS:
                adjacent = (rf"\b(?:{_CANON_ALT})\b{_LADDER_SEP}\b{rung}\b"
                            rf"|\b{rung}\b{_LADDER_SEP}\b(?:{_CANON_ALT})\b")
                if re.search(adjacent, l):
                    fail(rel(path), f"line {i}: `{rung}` used as a severity rung "
                                    f"next to the canonical ladder. The repo "
                                    f"ladder is {' > '.join(CANONICAL_LADDER)}; a "
                                    f"caller emitting a rung this skill never "
                                    f"names is silently ignored")
            if not any(marker in l.lower() for marker in GATE_MARKERS):
                continue
            named = [r for r in CANONICAL_LADDER if re.search(rf"\b{r}\b", l)]
            if not named:
                continue
            prefix = CANONICAL_LADDER[:len(named)]
            if named != prefix:
                missing = [r for r in prefix if r not in named]
                fail(rel(path), f"line {i}: gate names {named} but skips "
                                f"{missing}. A finding on the skipped rung "
                                f"passes the gate silently")


# --- pointer form (repo-wide) ----------------------------------------------

# A path not already anchored to the skill directory. The lookbehind rejects
# `${CLAUDE_SKILL_DIR}/references/...` and `<SKILL_DIR>/references/...`.
BARE_POINTER = re.compile(r"(?<![\w/}>-])(references|modes)/([a-z0-9._-]+\.md)")

# Verbs that make the path an instruction to open the file rather than a
# sentence about it. Third-person/participle forms (`loaded by main`, `reads`)
# are deliberately excluded — those only ever appear in descriptive tables.
_LOAD_VERB = re.compile(r".*\b(load|read|open|consult)\b(.*)$", re.I)
# All that may sit between the verb and the path. Anything else — a preposition,
# a clause ("read — is defined in") — means the sentence describes the file
# rather than instructing anyone to open it.
_LOAD_FILLER = re.compile(
    r"[\s`*:,]*(?:the|this|that|now|all|its|file|files|four)?[\s`*:,]*"
)


def _is_load_instruction(prefix_text):
    tail = re.sub(r"[`*_\s]+$", "", prefix_text)
    m = _LOAD_VERB.match(tail)
    return bool(m and _LOAD_FILLER.fullmatch(m.group(2)))


def check_pointer_form():
    """`Load references/x.md` resolves against the user's repo, not the skill
    directory, so it silently finds nothing and the skill answers from memory.
    `${CLAUDE_SKILL_DIR}/references/x.md` is the form that resolves.

    A DESCRIPTIVE mention is a different thing and must not be flagged: the
    `## Reference files` table row "`references/x.md` — holds P1-P11, loaded by
    Subagent A" is naming the file, not opening it. The discriminator is
    whether a load verb governs the path, not whether the path is bare."""
    for path in EVERY_MD:
        for i, l in enumerate(read(path) or [], 1):
            for m in BARE_POINTER.finditer(l):
                if not _is_load_instruction(l[:m.start()]):
                    continue
                fail(rel(path), f"line {i}: load instruction with a bare "
                                f"`{m.group(0)}`. It resolves against the user's "
                                f"repo, not the skill dir, and fails silently. "
                                f"Use ${{CLAUDE_SKILL_DIR}}/{m.group(0)}")


# --- orphan references (repo-wide) -----------------------------------------

BUNDLE_DIRS = ("references", "modes")
# `modes/<MODE>.md` is filled at runtime from a slug list declared in prose.
PARAMETERIZED = re.compile(r"\b(references|modes)/<[A-Za-z_]+>\.md")


def check_orphan_reference_files():
    """A file under references/ or modes/ that no SKILL.md points at is either
    dead weight or a disclosure the skill forgot to wire up."""
    for skill in SKILLS:
        body = "\n".join(read(skill / "SKILL.md") or [])
        for bundle in BUNDLE_DIRS:
            directory = skill / bundle
            if not directory.is_dir():
                continue
            named = set(re.findall(rf"{bundle}/([a-z0-9._-]+\.md)", body))
            if PARAMETERIZED.search(body):
                slugs = {s for l in body.split("\n") if "slug" in l.lower()
                         for s in re.findall(r"`([a-z0-9-]+)`", l)}
                named |= {f"{s}.md" for s in slugs}
            for f in sorted(directory.glob("*.md")):
                if f.name not in named:
                     warn(f"{skill.name}/{bundle}",
                         f"{f.name} is not pointed at by SKILL.md. It is a dead "
                         f"file or a disclosure that was never wired up")


# --- cross-skill duplication (repo-wide, WARN) -----------------------------

# One- and two-line fences are bare commands (`bun check-types`) that repeat
# across skills carrying no signal. Everything longer is hashed.
MIN_CODE_BLOCK_LINES = 3
MIN_PROSE_RUN_LINES = 5

# sha1[:12] of a normalized block -> why the duplication is accepted.
# Skills install independently and cannot import a shared file, so some copies
# are irreducible. Every entry MUST name its reason; an unexplained entry is
# indistinguishable from a silenced bug. Example of the shape:
#   "0123456789ab": "review-pr Phase 1 repo-map bash, copied into harden-plan —
#                    the two skills install separately and cannot share a file",
DUPLICATE_ALLOWLIST = {}


def _hash(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _blocks(path):
    """Yield (kind, first_line, line_count, normalized_text) for every fenced
    code block and every run of consecutive non-blank prose lines."""
    lines = read(path) or []
    fence, buf, start = None, [], 0
    run, run_start = [], 0
    for i, l in enumerate(lines, 1):
        m = re.match(r"^\s*(`{3,})(.*)$", l)
        if fence is None and m:
            if run:
                if len(run) >= MIN_PROSE_RUN_LINES:
                    yield "prose", run_start, len(run), "\n".join(run)
                run = []
            fence, buf, start = m.group(1), [], i
            continue
        if fence is not None:
            if m and len(m.group(1)) >= len(fence) and not m.group(2).strip():
                if len(buf) >= MIN_CODE_BLOCK_LINES:
                    yield "code", start, len(buf), "\n".join(buf)
                fence = None
            else:
                buf.append(l.rstrip())
            continue
        if l.strip():
            if not run:
                run_start = i
            run.append(l.rstrip())
        elif run:
            if len(run) >= MIN_PROSE_RUN_LINES:
                yield "prose", run_start, len(run), "\n".join(run)
            run = []
    if run and len(run) >= MIN_PROSE_RUN_LINES:
        yield "prose", run_start, len(run), "\n".join(run)


def check_cross_skill_duplication():
    """Byte-identical blocks living in 2+ skills. WARN, never FAIL: some of it
    is irreducible (skills install independently), some of it is a fork waiting
    to drift. Only a human can tell which, so this surfaces and does not block."""
    seen = {}
    for path in EVERY_MD:
        skill = rel(path).split("/")[0]
        for kind, line, count, text in _blocks(path):
            entry = seen.setdefault(_hash(text), {"kind": kind, "lines": count,
                                                  "sites": [], "skills": set()})
            entry["sites"].append(f"{rel(path)}:{line}")
            entry["skills"].add(skill)
    for digest, entry in sorted(seen.items(), key=lambda kv: -kv[1]["lines"]):
        if len(entry["skills"]) < 2 or digest in DUPLICATE_ALLOWLIST:
            continue
        warn("duplication",
             f"{entry['lines']}-line {entry['kind']} block [{digest}] is "
             f"byte-identical across {len(entry['skills'])} skills: "
             f"{', '.join(entry['sites'])}. Allowlist it with a reason if the "
             f"copy is deliberate")


# Below 5 normalized lines a shell block is boilerplate that legitimately recurs
# (`gh pr view ... --json`), and containment scores it 1.0 against anything that
# happens to contain it.
MIN_NEAR_DUPLICATE_LINES = 5

# The repo-map cluster scores 0.889-1.0 and the next-closest unrelated pair
# scores 0.611, so 0.85 sits in open space rather than on a knife edge.
NEAR_DUPLICATE_CONTAINMENT = 0.85


def _normalize_code(text):
    """Strip comment-only lines and per-line indentation. A copied block picks
    up a header comment naming its new caller and a different nesting depth,
    and that alone is enough to defeat the byte-identical hash above."""
    out = []
    for l in text.split("\n"):
        stripped = l.strip()
        if not stripped or (stripped.startswith("#") and not stripped.startswith("#!")):
            continue
        out.append(stripped)
    return out


def _containment(a, b):
    """Share of the SHORTER block's lines that also appear, in order, in the
    longer one. SequenceMatcher's own ratio halves that when the two differ in
    length, so a block pasted whole into a bigger one scores ~0.7 there and 1.0
    here — and pasted-whole is exactly the case worth catching."""
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / min(len(a), len(b))


def check_near_duplicate_code_blocks():
    """Same intent as the byte-identical check, one step looser: the repo-map
    bash, before it was given one home, was triplicated across fix-pr-review,
    harden-plan and review-pr and evaded that check because the copies differed
    by a leading comment, an indent, and one awk string. Clusters are keyed on
    the longest member's normalized digest so they can be allowlisted through
    DUPLICATE_ALLOWLIST like any other."""
    blocks = []
    for path in EVERY_MD:
        skill = rel(path).split("/")[0]
        for kind, line, _count, text in _blocks(path):
            if kind != "code":
                continue
            normalized = _normalize_code(text)
            if len(normalized) < MIN_NEAR_DUPLICATE_LINES:
                continue
            blocks.append((skill, f"{rel(path)}:{line}", normalized, _hash(text)))

    parent = list(range(len(blocks)))

    def root_of(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            a, b = blocks[i], blocks[j]
            if a[0] == b[0] or a[3] == b[3]:
                continue          # same skill, or already reported byte-identical
            if _containment(a[2], b[2]) >= NEAR_DUPLICATE_CONTAINMENT:
                parent[root_of(i)] = root_of(j)

    clusters = {}
    for i, block in enumerate(blocks):
        clusters.setdefault(root_of(i), []).append(block)
    for members in sorted(clusters.values(), key=lambda m: -max(len(b[2]) for b in m)):
        skills = {m[0] for m in members}
        if len(skills) < 2:
            continue
        longest = max(members, key=lambda m: len(m[2]))
        digest = _hash("\n".join(longest[2]))
        if digest in DUPLICATE_ALLOWLIST:
            continue
        sites = ", ".join(m[1] for m in sorted(members, key=lambda m: m[1]))
        warn("duplication",
             f"{len(longest[2])}-line code block [{digest}] is near-identical "
             f"across {len(skills)} skills once comments and indentation are "
             f"normalized: {sites}. The hash check above cannot see this one; "
             f"allowlist it with a reason if the copy is deliberate")


# --- global-rules mirror drift (WARN) --------------------------------------

# reference/CLAUDE.md:1 says it is a copy of the live global config. It has
# drifted silently twice. skills/simplify defers to its comment rule and
# skills/file-issue cites its board-ownership boundary, so a stale copy sends
# both to text that is no longer in force.
GLOBAL_RULES_MIRROR = ROOT.parent / "reference/CLAUDE.md"
LIVE_GLOBAL_RULES = pathlib.Path.home() / ".claude/CLAUDE.md"

# The mirror opens with a blockquote saying it IS a mirror, plus a blank line.
# The live file has no reason to carry that; everything after it must match.
MIRROR_PREAMBLE_LINES = 2
MAX_DRIFT_SECTIONS_REPORTED = 4

_SECTION_HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def _mirror_body(lines):
    preamble = lines[:MIRROR_PREAMBLE_LINES]
    if (len(preamble) == MIRROR_PREAMBLE_LINES
            and preamble[0].startswith(">") and not preamble[1].strip()):
        return lines[MIRROR_PREAMBLE_LINES:]
    return lines


def _enclosing_heading(lines, index):
    for l in reversed(lines[:min(index, len(lines)) + 1]):
        m = _SECTION_HEADING.match(l)
        if m:
            return m.group(1).strip()
    return "(above the first heading)"


def check_global_rules_mirror_drift():
    """The live file lives outside the repo, is machine-specific, and is absent
    in CI and on every other contributor's machine — so its absence is a skip,
    never a failure. Reports differing-line counts and the sections they land
    in; a full diff belongs in `diff`, not in a verifier line."""
    mirror = read(GLOBAL_RULES_MIRROR)
    if mirror is None:
        return
    live = read(LIVE_GLOBAL_RULES)
    if live is None:
        note("reference/CLAUDE.md",
             f"mirror drift check skipped. {LIVE_GLOBAL_RULES} is not on this "
             f"machine. The live file is user-local, so this check only runs "
             f"where it exists")
        return
    body = _mirror_body(mirror)
    mirror_only, live_only, sections = 0, 0, []
    matcher = difflib.SequenceMatcher(None, body, live, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        mirror_only += i2 - i1
        live_only += j2 - j1
        heading = (_enclosing_heading(body, i1) if i2 > i1
                   else _enclosing_heading(live, j1))
        if heading not in sections:
            sections.append(heading)
    if not sections:
        return
    hidden = len(sections) - MAX_DRIFT_SECTIONS_REPORTED
    shown = "; ".join(sections[:MAX_DRIFT_SECTIONS_REPORTED])
    warn("reference/CLAUDE.md",
         f"has drifted from {LIVE_GLOBAL_RULES}: {mirror_only} line(s) only in "
         f"the mirror, {live_only} only in the live file, across "
         f"{len(sections)} section(s), {shown}"
         f"{f' (+{hidden} more)' if hidden > 0 else ''}. Line 1 claims the file "
         f"is a copy and other skills cite it as one")


STATUS_ENUM = {"active", "resolved", "dismissed", "wontfix", "regression"}
BANNED_STATUS = {"still-active", "deferred"}

ALL_MD = sorted(
    list((ROOT / "review-pr").rglob("*.md")) + list((ROOT / "fix-pr-review").rglob("*.md"))
)


def check_banned_status_words():
    """A retired status value must not survive anywhere in either skill."""
    for path in ALL_MD:
        ls = read(path)
        for i, l in enumerate(ls or [], 1):
            for w in BANNED_STATUS:
                if re.search(rf"`{w}`", l):
                    fail(rel(path), f"line {i}: retired status value `{w}`")


def check_status_values():
    lines = read(SCHEMA)
    if not lines:
        fail("schema", "finding-state-schema.md missing")
        return
    declared = set()
    for l in lines:
        m = re.search(r"status:.*#\s*(.+)$", l)
        if m and "|" in m.group(1):
            declared = {x.strip().strip("`") for x in m.group(1).split("|")}
            break
    if not declared:
        fail("schema", "could not locate the status enum comment")
        return
    if declared != STATUS_ENUM:
        warn("schema", f"enum drifted from expected: {sorted(declared)}")
    for path in ALL_MD:
        ls = read(path)
        if not ls:
            continue
        for i, l in enumerate(ls, 1):
            for m in re.finditer(r"(?<![-\w])status:\s*([a-z][a-z-]*)", l):
                v = m.group(1)
                if v not in declared and v not in {"resolved", "regression"}:
                    fail(rel(path), f"line {i}: writes status `{v}` "
                                    f"not in enum {sorted(declared)}")


def check_cross_skill_fields():
    """Field names the two skills exchange must match exactly."""
    rp, fp = read(RP), read(FP)
    if not rp or not fp:
        return
    rp_t, fp_t = "\n".join(rp), "\n".join(fp)
    for field in ["class_completeness:", "inverse_risk", "Inverse risk:", "Class-sites:"]:
        in_rp, in_fp = field in rp_t, field in fp_t
        if in_rp and not in_fp:
            warn("cross-skill", f"`{field}` in review-pr but absent from fix-pr-review")
    if "class_sweep:" in fp_t:
        fail("cross-skill",
             "fix-pr-review still uses `class_sweep:`. Review-pr emits "
             "`class_completeness:`; the receiver cannot parse the sender")
    if "blast_radius" in fp_t:
        fail("cross-skill", "`blast_radius` should be retired (written once, read nowhere)")


def check_produced_fields_are_validated():
    """Any field a skill tells a subagent to emit should appear in its
    output-format block AND its validation list."""
    ls = read(FP)
    if not ls:
        return
    t = "\n".join(ls)
    for field in ["inverse_risk"]:
        produced = re.search(rf"- `{field}:`", t) or re.search(rf"{field}:", t)
        # crude but effective: the output-format block sits under "Output format"
        lines_t = t.split("\n")
        idx = next((i for i, l in enumerate(lines_t)
                    if l.startswith("## Output format")), None)
        if produced and idx is not None:
            window = "\n".join(lines_t[idx:idx + 100])
            if field not in window:
                fail("fix-pr-review",
                     f"`{field}` is produced but missing from the Output format block")
        validated = any(field in ln and re.search(r"MUST|must|fails validation", ln)
                        for ln in lines_t)
        if produced and not validated:
            fail("fix-pr-review", f"`{field}` is produced but never validated")


def check_dangling_refs():
    """Pointers to sibling skills that are not installed."""
    installed = {p.name for p in ROOT.iterdir() if p.is_dir() or p.is_symlink()}
    for path in EVERY_MD:
        ls = read(path)
        if not ls:
            continue
        for i, l in enumerate(ls, 1):
            for m in re.finditer(r"~/\.claude/skills/([a-z0-9-]+)", l):
                if m.group(1) not in installed:
                    fail(rel(path), f"line {i}: points at skill `{m.group(1)}` (not installed)")


# --- skill registry consistency (FAIL) -------------------------------------

def check_skill_registry():
    """`npx skills add` discovers `skills/<name>/SKILL.md` with `name` and
    `description` frontmatter, so a directory without one is invisible to the
    installer: a bare folder count then disagrees with `npx skills add -l`
    and nothing says why. Non-skill material lives outside `skills/` and is
    listed in the README Bundled-tooling table, so anything SKILL.md-less
    left directly under `skills/` is a packing error and fails here. This
    check keeps the registries in agreement so the next addition, rename, or
    removal cannot reintroduce the confusion silently: the SKILL.md set
    against the README Skills table and Usage block, with every non-skill
    directory under `skills/` accounted for in the Bundled-tooling table.
    Only flat, public skills are supported: a root SKILL.md, a nested one, or
    a `metadata.internal` hidden skill fails outright instead of slipping
    past the comparison."""
    readme_path = ROOT.parent / "README.md"
    try:
        readme = readme_path.read_text(encoding="utf-8")
    except OSError:
        fail("registry", f"{readme_path} is unreadable, cannot check the skill registry")
        return
    installable = {p.name for p in ROOT.iterdir()
                   if p.is_dir() and (p / "SKILL.md").exists()}
    present = {p.name for p in ROOT.iterdir() if p.is_dir()}
    tooling = present - installable

    if (ROOT.parent / "SKILL.md").exists():
        fail("registry", "a root SKILL.md exists. The installer discovers it, "
                         "but the README Skills table cannot name it and no "
                         "skill directory owns it. This repo supports only "
                         "flat skills under skills/")
    for path in sorted(ROOT.rglob("SKILL.md")):
        if path.parent.parent != ROOT:
            fail("registry", f"`{rel(path)}` is nested. The installer walks "
                             f"catalog layouts the README table does not "
                             f"model. This repo supports only flat "
                             f"`skills/<name>/SKILL.md` skills")
    for skill in SKILLS:
        lines = read(skill / "SKILL.md") or []
        frontmatter = ""
        if len(lines) > 1 and lines[0].strip() == "---":
            end = next((i for i, line in enumerate(lines[1:], 1)
                        if line.strip() == "---"), None)
            frontmatter = "\n".join(lines[1:end]) if end else ""
        if re.search(r"^\s*internal:\s*(true|yes|on)\b\s*(#.*)?$",
                      frontmatter, re.M | re.I):
            fail("registry", f"`{skill.name}` sets a truthy `metadata.internal`, "
                             f"so the default installer listing hides it while "
                             f"the README table shows it. This repo supports "
                             f"only public skills")

    def _section(head):
        start = readme.find(head)
        if start < 0:
            return None
        body = readme[start + len(head):]
        nxt = body.find("\n## ")
        return body[:nxt] if nxt >= 0 else body

    table_section = _section("## Skills (slash commands)")
    if table_section is None:
        fail("registry", "README has no `## Skills (slash commands)` section")
    else:
        table = set(re.findall(r"^\|\s*`([a-z0-9-]+)`", table_section, re.M))
        for name in sorted(installable - table):
            fail("registry", f"`{name}` has a SKILL.md but no row in the README "
                             f"Skills table, so the README undercounts what "
                             f"`npx skills add` installs")
        for name in sorted(table - installable):
            fail("registry", f"README Skills table lists `{name}` but "
                             f"`skills/{name}/SKILL.md` does not exist, so the "
                             f"README overcounts what `npx skills add` installs")

    usage_section = _section("## Usage")
    if usage_section is None:
        fail("registry", "README has no `## Usage` section, so the "
                         "slash-command index is missing entirely")
    else:
        commands = set(re.findall(r"^/([a-z0-9-]+)\b", usage_section, re.M))
        for name in sorted(installable - commands):
            fail("registry", f"`{name}` has a SKILL.md but no `/`-command line "
                             f"in the README Usage block, so an installed skill "
                             f"has no documented invocation")
        for name in sorted(commands - installable):
            fail("registry", f"README Usage block lists `/{name}` but "
                             f"`skills/{name}/SKILL.md` does not exist, so the "
                             f"documented command installs nothing")

    tooling_section = _section("## Bundled tooling")
    if tooling_section is None:
        if tooling:
            fail("registry", f"README has no `## Bundled tooling` section for "
                             f"{sorted(tooling)}")
    else:
        refs = set(re.findall(r"skills/([a-z0-9-]+)/?", tooling_section))
        for name in sorted(tooling):
            if name not in refs:
                fail("registry", f"`skills/{name}/` has no SKILL.md, so `npx skills "
                                 f"add` never lists it, but the README Bundled-tooling "
                                 f"table does not account for it either. A bare folder "
                                 f"count then disagrees with the installer with no "
                                 f"explanation. List it under `## Bundled tooling` or "
                                 f"give it a SKILL.md")
        for name in sorted(refs):
            if name not in present:
                fail("registry", f"README Bundled-tooling table points at "
                                 f"`skills/{name}/`, which does not exist")
            elif name in installable:
                fail("registry", f"`skills/{name}/` has a SKILL.md, so it is an "
                                 f"installable skill, but the README lists it as "
                                 f"bundled tooling")
        for name in sorted(set(re.findall(r"^\|\s*`([a-z0-9-]+)/`",
                                          tooling_section, re.M))):
            if not (ROOT.parent / name).is_dir():
                fail("registry", f"README Bundled-tooling table lists `{name}/` "
                                 f"but it does not exist at the repo root. The "
                                 f"bootstrap documentation points at nothing")

    note("registry", f"{len(installable)} installable skills "
                     f"({', '.join(sorted(installable))}); "
                     f"{len(tooling)} bundled-tooling director"
                     f"{'ies' if len(tooling) != 1 else 'y'} "
                     f"({', '.join(sorted(tooling)) or 'none'})")


def check_subagent_relative_paths():
    """A `references/...` path inside a fenced block is subagent-facing. Subagents
    inherit the user's repo as cwd, so a bare relative path silently resolves to
    nothing and the disclosure fails without any error."""
    for path in ALL_MD:
        ls = read(path)
        if not ls:
            continue
        depth = 0
        for i, l in enumerate(ls, 1):
            if re.match(r"^\s*`{3,}", l):
                depth ^= 1
                continue
            if depth and re.search(r"(?<!SKILL_DIR>/)(?<!/)\breferences/[a-z0-9-]+\.md", l):
                fail(rel(path), f"line {i}: bare `references/...` inside a prompt block. "
                                f"Subagents cannot resolve it; use <SKILL_DIR>/references/")


def check_forbidden_prefix_sync():
    """The reply-writer (triage subagent) and the reply-validator (main, Phase 7)
    load different files, so the forbidden-prefix list is deliberately duplicated.
    Deliberate duplication is only safe while something checks it stays in sync."""
    fp_root = ROOT / "fix-pr-review/references"
    rub, val = fp_root / "triage-rubric.md", fp_root / "github-reply-resolve.md"
    if not (rub.exists() and val.exists()):
        return
    words = lambda s: {w.strip().strip('"').strip("'") for w in re.split(r"[·,\n]", s)
                       if w.strip().strip('"').strip("'")}
    m = re.search(r"forbidden_prefixes\s*=\s*\[(.*?)\]", val.read_text(), re.S)
    if not m:
        fail("fix-pr-review", "github-reply-resolve.md: forbidden_prefixes list not found")
        return
    authoritative = words(m.group(1))
    rt = rub.read_text()
    b = re.search(r"`{3}\s*\n(\s*Thanks[^`]*?)`{3}", rt, re.S)
    if not b:
        fail("fix-pr-review",
             "triage-rubric.md no longer carries the forbidden-prefix list. The "
             "subagent writes replies it cannot see the spec for")
        return
    mirrored = words(b.group(1))
    if mirrored != authoritative:
        fail("fix-pr-review",
             f"forbidden-prefix lists drifted: only in rubric {sorted(mirrored - authoritative)}, "
             f"only in validator {sorted(authoritative - mirrored)}")


def check_reference_files_exist():
    for path in EVERY_MD:
        ls = read(path)
        if not ls:
            continue
        skill = skill_dir_of(path)
        for i, l in enumerate(ls, 1):
            for m in re.finditer(r"\b(references|modes)/([a-z0-9._-]+\.md)", l):
                prefix = l[:m.start()]
                sibling = re.search(r"\$\{CLAUDE_SKILL_DIR\}/\.\./([a-z0-9-]+)/$", prefix)
                owner = ROOT / sibling.group(1) if sibling else skill
                if not (owner / m.group(1) / m.group(2)).exists():
                    fail(rel(path), f"line {i}: {m.group(1)}/{m.group(2)} does not exist")


def check_step_refs():
    """A cross-reference to 'step N.M' must match a real heading."""
    for path in (RP, FP):
        ls = read(path)
        if not ls:
            continue
        heads = set()
        for l in ls:
            m = re.match(r"^\s*(?:#{2,4}\s+)?(?:STEP|Phase)\s+(\d+(?:\.\d+)?)\b", l, re.I) or re.match(r"^#{2,4}\s+(\d+(?:\.\d+)?)[.\s]", l)
            if m:
                heads.add(m.group(1))
        for i, l in enumerate(ls, 1):
            for m in re.finditer(r"\bstep (\d+\.\d+)\b", l, re.I):
                ctx = "\n".join(ls[max(0, i - 4):i + 2])
                if m.group(1) not in heads and "review-pr" not in ctx and "fix-pr-review" not in ctx:
                    warn(rel(path), f"line {i}: refers to step {m.group(1)}, no such heading")


def check_review_pr_ratio_naming():
    ls = read(RP)
    if not ls:
        return
    t = "\n".join(ls)
    n = len(re.findall(r"regression_share|cascade_share|`caused_by` share", t))
    names = set(re.findall(r"(regression_share|cascade_share)", t))
    if len(names) > 1:
        fail("review-pr", f"two names for one ratio: {sorted(names)}. Collapse to cascade_share")


def check_review_pr_severity_line():
    ls = read(RP)
    if not ls:
        return
    for i, l in enumerate(ls, 1):
        if "Severity wins" in l and "Critical" not in l:
            fail("review-pr", f"line {i}: severity ladder omits Critical. {l.strip()[:70]}")


MARKERS = {"FAIL": "x", "WARN": "!", "INFO": "-"}


def _emit(label, items):
    print(f"{label} ({len(items)}):")
    groups = {}
    for tag, msg in items:
        groups.setdefault(tag.split("/")[0], []).append((tag, msg))
    known = {s.name for s in SKILLS}
    for group in sorted(groups, key=lambda g: (g not in known, g)):
        print(f"\n  {group}")
        for tag, msg in groups[group]:
            where = tag[len(group) + 1:]
            print(f"    {MARKERS[label]} {where + ': ' if where else ''}{msg}")
    print()



# --- shell chain across bash fences (repo-wide, FAIL) ----------------------

BASH_FENCE = re.compile(r"^(\s*)(`{3,})bash\s*$")
ANY_FENCE_OPEN = re.compile(r"^\s*(`{3,})\S*\s*$")
SHELL_BUILTINS = {
    "IFS", "PATH", "HOME", "PWD", "OLDPWD", "SHELL", "USER", "PS1", "PS2",
    "RANDOM", "REPLY", "SECONDS", "LINENO", "BASH_SOURCE", "FUNCNAME",
    "GITHUB_TOKEN", "GH_TOKEN", "EDITOR", "TMPDIR", "LANG", "LC_ALL",
}


def _fenced_spans(lines):
    """Yield (open_index, close_index, ticks, is_bash) for every fenced block.

    A closing fence must be at least as long as the one that opened it, which is
    what lets a four-backtick block legally contain three-backtick fences."""
    out, i = [], 0
    while i < len(lines):
        m = ANY_FENCE_OPEN.match(lines[i])
        if not m:
            i += 1
            continue
        ticks = m.group(1)
        is_bash = bool(BASH_FENCE.match(lines[i]))
        j = i + 1
        while j < len(lines):
            c = re.match(rf"^\s*{ticks[0]}{{{len(ticks)},}}\s*$", lines[j])
            if c:
                break
            j += 1
        out.append((i, min(j, len(lines)), ticks, is_bash))
        i = j + 1
    return out


def _bash_blocks(lines):
    """Yield (first_body_line_number, body_lines) for every bash fence.

    The line number is 1-based and points at the first line of the body, not at
    the fence, so a reported finding lands on the offending command."""
    return [(o + 2, lines[o + 1:c]) for o, c, _t, is_bash in _fenced_spans(lines)
            if is_bash]


def check_placeholder_consistency():
    """`$NAME` means an earlier block put it in this shell; `<NAME>` means the
    reader substitutes it here. A name written both ways means one of the two
    is dead, and nothing reports which. That is how a producer block can set a
    variable no consumer ever reads while the document still looks wired up."""
    for path in EVERY_MD:
        lines = read(path) or []
        shell, token = set(), set()
        for _, body in _bash_blocks(lines):
            text = "\n".join(body)
            shell |= set(re.findall(r"\$\{?([A-Z][A-Z0-9_]{1,})\b", text))
            token |= set(re.findall(r"<([A-Z][A-Z0-9_]{1,})>", text))
        for name in sorted((shell & token) - SHELL_BUILTINS):
            fail(rel(path),
                 f"`{name}` is written as both `${name}` and `<{name}>` in bash "
                 f"blocks. One form is dead: either the assignment has no reader "
                 f"or the paste token has no producer. Pick one and say which in "
                 f"prose")


def check_bash_block_chain():
    """Derived from the fence bodies, so there is no declaration to fall out of
    date. Catches the three shapes that survived nine review rounds on
    triage-board: a function defined and never called, and a variable read with
    no assignment anywhere and no `:?` guard to fail loudly when it is unset.

    A function named anywhere in the prose counts as called. review-pr defines
    a cleanup helper and invokes it only from instruction text, which is a
    legitimate shape in a document meant for an agent to follow.

    A variable assigned and read inside one block is ordinary and is not
    reported; requiring the read to land in a later block flagged 55 legitimate
    uses across the repo and buried the three real findings.

    The unset-read rule warns rather than fails. Several skills assign a value
    in prose and read it in a fence, which is a real gap but an established
    convention, and failing 15 pre-existing instances would gate every future
    PR on other people's skills."""
    for path in EVERY_MD:
        lines = read(path) or []
        blocks = _bash_blocks(lines)
        if not blocks:
            continue
        assigned, read_at, guarded = {}, {}, {}
        defined, called = {}, set()
        for start, body in blocks:
            text = "\n".join(body)
            for offset, line in enumerate(body):
                at = start + offset
                for m in re.finditer(
                        r"(?:^|[;&|]|\b(?:then|do|else)\s)\s*([A-Z][A-Z0-9_]{1,})=",
                        line):
                    assigned.setdefault(m.group(1), (at, m.start(1)))
                for m in re.finditer(r"\$\{([A-Z][A-Z0-9_]{1,}):[?]", line):
                    guarded.setdefault(m.group(1), (at, m.start(1)))
                for m in re.finditer(r"\$\{?([A-Z][A-Z0-9_]{1,})\b", line):
                    read_at.setdefault(m.group(1), (at, m.start(1)))
            for m in re.finditer(r"^\s*([a-z_][a-z0-9_]*)\s*\(\)\s*\{", text, re.M):
                defined.setdefault(m.group(1), start)
            for line in text.split("\n"):
                if re.match(r"^\s*[a-z_][a-z0-9_]*\s*\(\)", line):
                    continue
                m = re.match(r"^\s*([a-z_][a-z0-9_]*)\b", line)
                if m:
                    called.add(m.group(1))
                called |= set(re.findall(r"[|&]{2}\s*([a-z_][a-z0-9_]*)\b", line))

        for name, pos in sorted(read_at.items()):
            if name in SHELL_BUILTINS:
                continue
            r_line = pos[0]
            a = assigned.get(name)
            g = guarded.get(name)
            if (a is not None and a <= pos) or (g is not None and g <= pos):
                continue
            warn(rel(path),
                 f"`${name}` is read at line {r_line} with no `{name}=` in any "
                 f"bash block and no `${{{name}:?}}` guard. Unset it expands to "
                 f"empty and the command runs against the wrong target instead "
                 f"of failing. WARN rather than FAIL because several skills "
                 f"assign in prose and read in a fence by convention")

        fenced = set()
        for o, c, _t, _b in _fenced_spans(lines):
            fenced |= set(range(o, min(c, len(lines)) + 1))
        prose = "\n".join(l for i, l in enumerate(lines) if i not in fenced)
        for name, d_line in sorted(defined.items()):
            if name in called or re.search(rf"\b{re.escape(name)}\b", prose):
                continue
            fail(rel(path),
                 f"`{name}()` is defined at line {d_line} and never called. A "
                 f"function nothing invokes is the defect this check exists for")


def main():
    if not SKILLS:
        fail("setup", f"no skills found under {ROOT}")

    for skill in SKILLS:
        for path in SKILL_MD[skill.name]:
            check_fences(path, read(path) or [])

    for p in (RP, FP, SCHEMA):
        ls = read(p)
        if ls is None:
            fail("setup", f"missing {p}")
            continue
        check_nested_prompt(p, ls)

    check_frontmatter()
    check_description_budget()
    check_orphan_model_invocation()
    check_progressive_disclosure()
    check_pointer_form()
    check_severity_ladder_consistency()
    check_orphan_reference_files()
    check_reference_files_exist()
    check_dangling_refs()
    check_skill_registry()
    check_cross_skill_duplication()
    check_near_duplicate_code_blocks()
    check_global_rules_mirror_drift()
    check_placeholder_consistency()
    check_bash_block_chain()

    check_status_values()
    check_banned_status_words()
    check_cross_skill_fields()
    check_produced_fields_are_validated()
    check_field_chains()
    check_required_field_in_all_item_blocks()
    check_compute_before_read()
    check_forbidden_prefix_sync()
    check_subagent_relative_paths()
    check_step_refs()
    check_review_pr_ratio_naming()
    check_review_pr_severity_line()

    chars, invoked, opted_out = description_budget()
    print(f"  {len(SKILLS)} skills, {len(EVERY_MD)} markdown files under {ROOT}")
    print(f"  {chars:,} description chars always in context across {invoked} "
          f"model-invoked skills; {opted_out} user-invoked "
          f"(`disable-model-invocation: true`) cost nothing")
    print()
    if fails:
        _emit("FAIL", fails)
    if warns:
        _emit("WARN", warns)
    if notes:
        _emit("INFO", notes)
    if not fails and not warns:
        print("all checks pass")
        print()
    return 1 if fails else 0




# ---------------------------------------------------------------------------
# Relational checks. Every defect that survived three "verified green" rounds
# was relational: a field produced in one file, validated in a second, consumed
# in a third, with one link missing. Textual checks cannot see those.
# Scoped to review-pr + fix-pr-review: these field chains exist nowhere else.
# ---------------------------------------------------------------------------

# Fields that must complete a produce -> validate -> consume chain.
# Fields an agent is instructed to EMIT. `cascade_share` and `fix_status` are
# excluded deliberately: they are computed/internal, never emitted in a template.
TRACED_FIELDS = [
    "inverse_risk", "class_completeness", "reusability_context",
    "caused_by", "class_sites", "depends_on",
]

ITEM_BLOCKS = ["## FIX", "## DISMISS", "## DEFER", "## DISAGREE"]


def _emitted(field):
    """A field is emitted if some template line assigns it: `  field: <...>`.
    That is what an output template looks like, in any file, fenced or not."""
    out = []
    for path in ALL_MD:
        for i, l in enumerate(read(path) or [], 1):
            if re.match(rf"^\s*{re.escape(field)}:", l):
                out.append(f"{rel(path)}:{i}")
    return out


def _required(field):
    out = []
    for path in ALL_MD:
        for i, l in enumerate(read(path) or [], 1):
            if field in l and re.search(r"\bMUST\b|fails validation", l):
                out.append(f"{rel(path)}:{i}")
    return out


def check_field_chains():
    """Validated-but-never-emitted is the high-signal case: the validator
    rejects every plan because nothing was ever told to produce the field."""
    for field in TRACED_FIELDS:
        req, emit = _required(field), _emitted(field)
        if req and not emit:
            fail("chain", f"`{field}` is required at {req[0]} but no template "
                          f"anywhere emits it. Validation can never pass")


def check_required_field_in_all_item_blocks():
    """A field required of EVERY item must appear in every item block of the
    triage template, not just the FIX block."""
    tmpl = ROOT / "fix-pr-review/references/triage-prompt.md"
    ls = read(tmpl)
    if not ls:
        return
    required = set()
    for path in ALL_MD:
        for l in read(path) or []:
            if re.search(r"[Ee]very item.*MUST", l):
                required.update(re.findall(r"`([a-z_]+)`", l))
    if not required:
        return
    # map each item block to its line span
    spans, cur = {}, None
    for i, l in enumerate(ls, 1):
        if l.strip() in ITEM_BLOCKS or any(l.startswith(b + " ") for b in ITEM_BLOCKS):
            cur = next(b for b in ITEM_BLOCKS if l.startswith(b))
            spans[cur] = [i, len(ls)]
        elif cur and re.match(r"^## ", l) and not any(l.startswith(b) for b in ITEM_BLOCKS):
            spans[cur][1] = i; cur = None
    for field in sorted(required):
        for block, (s, e) in spans.items():
            body = "\n".join(ls[s:e])
            if field not in body:
                fail("chain", f"`{field}` is required of every item but is absent "
                              f"from the `{block}` block of triage-prompt.md "
                              f"(lines {s}-{e}). The plan fails validation and aborts")


def check_compute_before_read():
    """Track which phase each line sits in, then flag any line that defers to a
    value 'computed in Phase N' when N is later than the phase doing the reading.
    Phases run in order, so a forward reference is a value that does not exist."""
    for path in ALL_MD:
        ls = read(path) or []
        cur = None
        for i, l in enumerate(ls, 1):
            m = re.match(r"^#{1,3} Phase (\d)", l)
            if m:
                cur = int(m.group(1))
                continue
            if cur is None:
                continue
            for c in re.finditer(r"computed in Phase (\d)", l):
                target = int(c.group(1))
                if target > cur:
                    fail(rel(path),
                         f"line {i}: Phase {cur} defers to a value \"computed in "
                         f"Phase {target}\". Phase {cur} runs first, so it does not "
                         f"exist yet: {l.strip()[:70]}")


if __name__ == "__main__":
    sys.exit(main())
