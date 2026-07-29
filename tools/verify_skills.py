#!/usr/bin/env python3
"""Structural verifier for review-pr / fix-pr-review.

Exists because a naive fence COUNT gave a false pass while the prompt template
was actually broken: an inner ``` closed the outer fence, silently ejecting 54
lines of output-format spec out of the prompt. Count parity is not nesting.
"""
import re, sys, pathlib

ROOT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 \
    else pathlib.Path.home() / ".agents/skills"
RP = ROOT / "review-pr/SKILL.md"
FP = ROOT / "fix-pr-review/SKILL.md"
SCHEMA = ROOT / "review-pr/references/finding-state-schema.md"

fails, warns = [], []


def rel(p):
    return f"{p.parent.name}/{p.name}" if hasattr(p, "parent") else str(p)


def fail(t, m): fails.append(f"[{t}] {m}")
def warn(t, m): warns.append(f"[{t}] {m}")


def read(p):
    return p.read_text(encoding="utf-8").split("\n") if p.exists() else None


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
                     f"{inner} inner fence(s) — the first inner fence CLOSES it. "
                     f"Use {'`' * (open_len + 1)} for the outer fence.")
            open_at = None
        else:
            inner += 1


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
             "fix-pr-review still uses `class_sweep:` — review-pr emits "
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
    for path in (RP, FP):
        ls = read(path)
        if not ls:
            continue
        for i, l in enumerate(ls, 1):
            for m in re.finditer(r"~/\.claude/skills/([a-z0-9-]+)", l):
                if m.group(1) not in installed:
                    fail(rel(path), f"line {i}: points at skill `{m.group(1)}` (not installed)")


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
                fail(rel(path), f"line {i}: bare `references/...` inside a prompt block "
                                f"— subagents cannot resolve it; use <SKILL_DIR>/references/")


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
             "triage-rubric.md no longer carries the forbidden-prefix list — the "
             "subagent writes replies it cannot see the spec for")
        return
    mirrored = words(b.group(1))
    if mirrored != authoritative:
        fail("fix-pr-review",
             f"forbidden-prefix lists drifted: only in rubric {sorted(mirrored - authoritative)}, "
             f"only in validator {sorted(authoritative - mirrored)}")


def check_reference_files_exist():
    for path in (RP, FP):
        ls = read(path)
        if not ls:
            continue
        for i, l in enumerate(ls, 1):
            for m in re.finditer(r"references/([a-z0-9-]+\.md)", l):
                if not (path.parent / "references" / m.group(1)).exists():
                    fail(rel(path), f"line {i}: references/{m.group(1)} does not exist")


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


def check_duplicate_ratio():
    ls = read(RP)
    if not ls:
        return
    t = "\n".join(ls)
    n = len(re.findall(r"regression_share|cascade_share|`caused_by` share", t))
    names = set(re.findall(r"(regression_share|cascade_share)", t))
    if len(names) > 1:
        fail("review-pr", f"two names for one ratio: {sorted(names)} — collapse to cascade_share")


def check_severity_ladder():
    ls = read(RP)
    if not ls:
        return
    for i, l in enumerate(ls, 1):
        if "Severity wins" in l and "Critical" not in l:
            fail("review-pr", f"line {i}: severity ladder omits Critical — {l.strip()[:70]}")


def main():
    for p in (RP, FP, SCHEMA):
        ls = read(p)
        if ls is None:
            fail("setup", f"missing {p}")
            continue
        check_fences(p, ls)
        check_nested_prompt(p, ls)
    check_status_values()
    check_banned_status_words()
    check_cross_skill_fields()
    check_produced_fields_are_validated()
    check_dangling_refs()
    check_field_chains()
    check_required_field_in_all_item_blocks()
    check_compute_before_read()
    check_forbidden_prefix_sync()
    check_subagent_relative_paths()
    check_reference_files_exist()
    check_step_refs()
    check_duplicate_ratio()
    check_severity_ladder()

    for p in (RP, FP):
        if p.exists():
            print(f"  {p.parent.name}/{p.name}: {len(read(p))} lines")
    print()
    if fails:
        print(f"FAIL ({len(fails)}):")
        for f in fails:
            print("  x", f)
    if warns:
        print(f"\nWARN ({len(warns)}):")
        for w in warns:
            print("  !", w)
    if not fails and not warns:
        print("all checks pass")
    print()
    return 1 if fails else 0




# ---------------------------------------------------------------------------
# Relational checks. Every defect that survived three "verified green" rounds
# was relational: a field produced in one file, validated in a second, consumed
# in a third, with one link missing. Textual checks cannot see those.
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
                          f"anywhere emits it — validation can never pass")


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
                              f"(lines {s}-{e}) — the plan fails validation and aborts")


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
                         f"Phase {target}\" — Phase {cur} runs first, so it does not "
                         f"exist yet: {l.strip()[:70]}")


if __name__ == "__main__":
    sys.exit(main())
