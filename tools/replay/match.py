#!/usr/bin/env python3
"""Match a replayed finding to a frozen benchmark record, and say how sure it is.

Exact `(file, line)` equality does not work here. Line numbers drift between the commit
a verdict was adjudicated against and the commit a replay reads; the skill rewords its
own claims run to run; and a legitimate finding can anchor a dozen lines off the
construct it describes. So the matcher scores three independent signals and refuses to
collapse a weak match into a confident one.

The one thing it must never do is discard. A harness that drops the findings it cannot
place and reports precision on what is left is measuring its own matcher, not the skill.
Everything unplaced comes back in `unmatched` and `ambiguous` and is reported.
"""
import functools
import re

# Below AMBIGUOUS the pair is not the same finding. Between AMBIGUOUS and ACCEPT it might
# be, which is not good enough to grade a verdict on — those land in their own bucket and
# are excluded from precision rather than guessed at.
ACCEPT = 0.60
AMBIGUOUS = 0.42

# Two findings on the same construct routinely anchor a hunk apart. 25 lines is roughly
# one screen: wide enough to absorb that, narrow enough that two unrelated functions in
# the same file do not collide.
LINE_WINDOW = 25

WEIGHTS = {"path": 0.30, "line": 0.20, "claim": 0.50}

# An anchor naming several sites, or a pattern covering many files, was resolved to its
# first concrete path by the loader. Agreeing with that one path is therefore weaker
# evidence than agreeing with an anchor that only ever named one file.
ANCHOR_CONFIDENCE = {"multi": 0.80, "glob": 0.60}

# Containment over a handful of tokens is arithmetic, not evidence: one word lands inside
# any long write-up. Below this much staked vocabulary a recall hit is scaled down toward
# the noise it actually is.
MIN_CLAIM_EVIDENCE = 5

_STOP = frozenset("""a an the is are was were be been being of on in to for from with
and or but not no if it its this that these those as at by via when where which who
does do did done has have had will would should could can may might there their they
you your we our i he she them then than so such only also more most other another same
new old add adds added use uses used using make makes made get gets got set sets
""".split())

_WORD = re.compile(r"[a-z0-9]+")
# Identifiers carry far more matching signal than prose: two findings about
# `resolveTenantScope` are almost certainly the same finding however differently the
# sentence around it is phrased. Case-sensitive and >=4 chars keeps out English words.
_IDENT = re.compile(r"\b(?:[a-z]+[A-Z]\w*|[A-Z][a-z]+[A-Z]\w*|\w*_\w+)\b|`([^`]+)`")


# Tokenising is the harness's hot loop: the permutation null re-scores every claim
# against every defect once per permutation, and a null needs enough permutations to
# carry a p-value. Frozen returns so a cached set cannot be mutated by a caller.
@functools.lru_cache(maxsize=16384)
def _words(text):
    return frozenset(w for w in _WORD.findall((text or "").lower())
                     if w not in _STOP and len(w) > 2)


@functools.lru_cache(maxsize=16384)
def _idents(text):
    found = set()
    for m in _IDENT.finditer(text or ""):
        token = m.group(1) or m.group(0)
        for part in re.split(r"[^\w]+", token):
            if len(part) >= 4:
                found.add(part)
    return frozenset(found)


def _jaccard(a, b):
    if not a or not b:
        return None
    return len(a & b) / len(a | b)


def claim_score(a, b):
    jw = _jaccard(_words(a), _words(b))
    ji = _jaccard(_idents(a), _idents(b))
    if jw is None and ji is None:
        return None
    if ji is None:
        return jw
    if jw is None:
        return ji
    return 0.45 * jw + 0.55 * ji


def _containment(claim_tokens, text_tokens):
    """How much of the CLAIM landed inside the text — asymmetric, claim on the bottom.

    Dividing by the shorter side instead lets a one-word claim score a perfect 1.000
    against a long root-cause write-up, which is the direction recall is measured in.
    """
    if not claim_tokens or not text_tokens:
        return None
    return len(claim_tokens & text_tokens) / float(len(claim_tokens))


def recall_score(finding_claim, defect_text):
    """Score a one-sentence finding against a multi-paragraph root-cause write-up.

    Jaccard is the wrong shape here: the union is dominated by the long side, so a
    finding that names the defect exactly still scores near zero. Containment asks the
    question that actually matters for recall — did the short text land inside the
    long one — and stays comparable across defects of wildly different write-up length.

    Scaled by how much vocabulary the claim staked, because containment is trivially 1.0
    for a claim short enough to be swallowed whole by any paragraph of prose.
    """
    claim_words, claim_idents = _words(finding_claim), _idents(finding_claim)
    cw = _containment(claim_words, _words(defect_text))
    ci = _containment(claim_idents, _idents(defect_text))
    if cw is None and ci is None:
        return 0.0
    if ci is None:
        contained = cw
    elif cw is None:
        contained = ci
    else:
        contained = 0.40 * cw + 0.60 * ci
    evidence = min(1.0, (len(claim_words) + len(claim_idents)) / float(MIN_CLAIM_EVIDENCE))
    return contained * evidence


def path_score(a, b):
    """None means 'no path to compare'; 0.0 means 'compared and they are different files'."""
    if not a or not b:
        return None
    a, b = a.replace("\\", "/"), b.replace("\\", "/")
    if a == b:
        return 1.0
    pa, pb = a.split("/"), b.split("/")
    if pa[-1] != pb[-1]:
        return 0.0
    # Same filename in different trees is common in a monorepo (`route.ts`, `index.ts`),
    # so the parent directory has to agree before a basename hit counts as strong.
    return 0.85 if len(pa) > 1 and len(pb) > 1 and pa[-2] == pb[-2] else 0.70


def line_score(a, b, window=LINE_WINDOW):
    if a is None or b is None:
        return None
    return max(0.0, 1.0 - abs(int(a) - int(b)) / float(window))


def _anchor_confidence(replay, frozen):
    """The weaker of the two anchors governs — a multi-site anchor cannot be made precise
    by being compared against a precise one."""
    return min(ANCHOR_CONFIDENCE.get(replay.get("anchor_quality"), 1.0),
               ANCHOR_CONFIDENCE.get(frozen.get("anchor_quality"), 1.0))


def score_pair(replay, frozen, window=LINE_WINDOW):
    """Composite score plus the per-signal breakdown that justifies it."""
    if replay.get("pr") is not None and frozen.get("pr") is not None:
        if int(replay["pr"]) != int(frozen["pr"]):
            return 0.0, {"reject": "different PR"}
    ps = path_score(replay.get("path"), frozen.get("path"))
    if ps == 0.0:
        return 0.0, {"reject": "different file"}
    if ps is not None:
        ps *= _anchor_confidence(replay, frozen)
    cs = claim_score(replay.get("claim"), frozen.get("claim"))
    ls = line_score(replay.get("line_start"), frozen.get("line_start"), window)
    parts = {"path": ps, "line": ls, "claim": cs}
    live = {k: v for k, v in parts.items() if v is not None}
    if not live:
        return 0.0, {"reject": "nothing comparable"}
    # Renormalising over the signals that exist stops a missing line number from reading
    # as a disagreement — absent evidence is not contrary evidence. The claim is the
    # exception, and keeps its weight in the denominator either way: it is the only
    # signal carrying what the finding actually SAYS, so renormalising it away lets a
    # content-free row ride path and line to a perfect score and evict the real finding
    # from the greedy assignment.
    total = sum(WEIGHTS[k] for k in live) + (0.0 if cs is not None else WEIGHTS["claim"])
    return sum(WEIGHTS[k] * v for k, v in live.items()) / total, parts


def match(replays, frozens, window=LINE_WINDOW, accept=ACCEPT, ambiguous=AMBIGUOUS):
    """Greedy one-to-one assignment, highest score first.

    One-to-one matters for precision: a run that emits five rewordings of the same
    finding must not have all five absorbed by one CORRECT verdict, or duplication
    scores as accuracy. Surplus copies fall out as unmatched, where they are visible.
    """
    pairs = []
    for i, r in enumerate(replays):
        for j, f in enumerate(frozens):
            s, parts = score_pair(r, f, window)
            if s >= ambiguous:
                pairs.append((s, i, j, parts))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))

    taken_r, taken_f = set(), set()
    matched, unsure = [], []
    for s, i, j, parts in pairs:
        if i in taken_r or j in taken_f:
            continue
        taken_r.add(i)
        taken_f.add(j)
        (matched if s >= accept else unsure).append(
            {"replay": replays[i], "frozen": frozens[j], "score": round(s, 4),
             "signals": {k: (round(v, 3) if isinstance(v, float) else v)
                         for k, v in parts.items()}})
    return {
        "matched": matched,
        "ambiguous": unsure,
        "unmatched_replay": [r for i, r in enumerate(replays) if i not in taken_r],
        "unmatched_frozen": [f for j, f in enumerate(frozens) if j not in taken_f],
    }
