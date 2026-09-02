#!/usr/bin/env python3
"""Score a piece of writing for the AI tells unslop names, so a register claim can carry a
number instead of an assertion.

This is a floor on slop, never a ceiling. It counts the ~20 of unslop's 31 rules that a
regex can settle and reports two continuous measures that no word list detects: how uniform
the sentence lengths are, and how nominalised the prose is. Those two are what issue #37 is
actually about. A skill written as dense spec prose is not detectable by counting `delve`.

Read a score as a comparison, never as an absolute. Several rules here over-count on
purpose, passive voice most of all. A systematic false positive lands in both arms of an
A/B run and cancels in the delta, which is the only number worth acting on.

    python3 tools/eval/slop_score.py FILE [FILE ...]
    python3 tools/eval/slop_score.py --json FILE
    python3 tools/eval/slop_score.py --check-drift
"""
import argparse
import json
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
RULES_FILE = HERE / "slop_rules.json"
# Both roots are live install locations on a machine that uses these skills, so checking
# only the first prints "not on this machine" while the file sits in the second.
LIVE_UNSLOP_CANDIDATES = (
    pathlib.Path.home() / ".claude" / "skills" / "unslop" / "SKILL.md",
    pathlib.Path.home() / ".agents" / "skills" / "unslop" / "SKILL.md",
)

# CommonMark allows three or more delimiters and a closing run at least as long as the
# opening one, so a four-backtick block (used to fence content that itself contains a fence)
# is not matched by a three-only pattern and its code would be scored as prose.
# Group 2 pins the delimiter character so the closing run can only extend with more of the
# same one. Allowing backticks and tildes to mix let a `````~~~` line close a backtick block,
# which CommonMark reads as code content, ending the block early and scoring the rest as prose.
# An unclosed fence runs to end of document per CommonMark, which is also what a truncated
# answer leaves behind. Without the \Z arm the pattern matched nothing and the code inside
# was scored as prose, the opposite of the intended direction.
FENCE = re.compile(r"^[ \t]*((`|~)\2{2,})([^\n`]*)\n(.*?)(?:^[ \t]*\1\2*[ \t]*$|\Z)",
                   re.MULTILINE | re.DOTALL)
# A model fences the deliverable in ```markdown to be copy-pasted and the title in a bare
# fence, so stripping every fence scores the commentary instead of the artifact.
CODE_LANGUAGES = frozenset({
    "diff", "patch", "js", "javascript", "jsx", "ts", "typescript", "tsx", "python", "py",
    "bash", "sh", "shell", "zsh", "fish", "console", "json", "jsonc", "yaml", "yml", "toml",
    "ini", "sql", "go", "rust", "rs", "java", "kotlin", "swift", "c", "cpp", "csharp", "cs",
    "ruby", "rb", "php", "perl", "lua", "r", "scala", "html", "css", "scss", "xml", "svg",
    "dockerfile", "docker", "make", "makefile", "cmake", "graphql", "proto", "hcl", "tf",
})
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\s\n]+")
LONG_SENTENCE_WORDS = 35


def load_rules(path=RULES_FILE):
    spec = json.loads(path.read_text())
    compiled = []
    for rule in spec["rules"]:
        kind = rule["kind"]
        if kind == "regex":
            pattern = rule["pattern"]
        elif kind == "words":
            pattern = r"\b(" + "|".join(re.escape(t) for t in rule["terms"]) + r")\b"
        elif kind == "phrases":
            pattern = "|".join(re.escape(t) for t in rule["terms"])
        else:
            raise ValueError(f"rule {rule['id']} has unknown kind {kind!r}")
        compiled.append({
            "id": rule["id"],
            "name": rule["name"],
            "regex": re.compile(pattern, re.IGNORECASE),
        })
    if not compiled:
        raise ValueError(f"{path} defines no rules; a scorer with no rules reports 0 for "
                         f"everything and looks like a clean result")
    return compiled, spec["measures"]


def strip_code(text):
    """Drop fenced code, keep fenced prose unwrapped.

    A long code block would otherwise dilute every per-100-word rate and make a code-heavy
    answer look cleaner than a prose one. But a fence holding the deliverable is the thing
    being measured, so language decides: a named code language goes, anything else stays.
    """
    def replace(match):
        language = match.group(3).strip().lower().split(":")[0]
        return "\n" if language in CODE_LANGUAGES else "\n" + match.group(4) + "\n"

    return FENCE.sub(replace, text)


def sentences(prose):
    found = [s.strip() for s in SENTENCE_SPLIT.split(prose) if s.strip()]
    return [s for s in found if WORD.search(s)]


def score(text, rules=None, measures=None):
    """Return per-rule counts and continuous measures for one piece of writing."""
    if rules is None or measures is None:
        rules, measures = load_rules()

    prose = strip_code(text)
    words = WORD.findall(prose)
    total_words = len(words)
    per_100 = (lambda n: round(100.0 * n / total_words, 2)) if total_words else (lambda n: 0.0)

    hits = {}
    covered = set()
    for rule in rules:
        spans = [m.span() for m in rule["regex"].finditer(prose)]
        hits[rule["name"]] = {"count": len(spans), "per_100w": per_100(len(spans))}
        covered.update(spans)
    # Per-rule counts stay raw for diagnostics; the total counts each span once. Terms filed
    # under two rules on purpose would otherwise weight double against every other tell.
    total_tells = len(covered)

    lengths = [len(WORD.findall(s)) for s in sentences(prose)]
    lowered = [w.lower() for w in words]
    exceptions = set(measures["adverb_exceptions"])
    adverbs = [w for w in lowered if w.endswith("ly") and w not in exceptions and len(w) > 4]
    suffixes = tuple(measures["nominalisation_suffixes"])
    nominalisations = [w for w in lowered if w.endswith(suffixes) and len(w) > 5]

    return {
        "words": total_words,
        "sentences": len(lengths),
        "rules": hits,
        "tells_per_100w": round(total_tells * 100.0 / total_words, 2) if total_words else 0.0,
        "measures": {
            "mean_sentence_words": round(statistics.fmean(lengths), 2) if lengths else 0.0,
            # Uniform sentence length is the register tell unslop's "vary rhythm" names, and
            # it is invisible to every word list above. Low spread means machine cadence.
            "sentence_words_stdev": round(statistics.stdev(lengths), 2) if len(lengths) > 1
            else 0.0,
            "pct_sentences_over_35w": round(
                100.0 * sum(n > LONG_SENTENCE_WORDS for n in lengths) / len(lengths), 1)
            if lengths else 0.0,
            "adverb_per_100w": per_100(len(adverbs)),
            "nominalisation_per_100w": per_100(len(nominalisations)),
        },
    }


def delta(before, after):
    """Per-metric change from before to after. Negative means less slop."""
    out = {"tells_per_100w": round(after["tells_per_100w"] - before["tells_per_100w"], 2),
           "rules": {}, "measures": {}}
    for name in before["rules"]:
        change = after["rules"][name]["per_100w"] - before["rules"][name]["per_100w"]
        if change:
            out["rules"][name] = round(change, 2)
    for name in before["measures"]:
        out["measures"][name] = round(after["measures"][name] - before["measures"][name], 2)
    return out


# Rule 7 has always listed a dozen-plus terms, so a shorter capture means the regex clipped
# the list and the drift check would pass while comparing nothing.
MIN_PLAUSIBLE_VOCABULARY = 8


def extract_live_vocabulary(text):
    """Pull unslop rule 7's word list out of the live SKILL.md, or None if its shape moved."""
    match = re.search(r"\*\*AI vocabulary\.\*\*\s*(.+?)\s*Replace", text, re.DOTALL)
    if not match:
        return None
    terms = set()
    for chunk in match.group(1).split(","):
        cleaned = re.sub(r"\(.*?\)", "", chunk).strip().strip(".").lower()
        if cleaned:
            terms.add(cleaned)
    if len(terms) < MIN_PLAUSIBLE_VOCABULARY:
        return None
    return terms


def find_live_unslop():
    """The installed unslop skill, or None when it is not on this machine."""
    return next((path for path in LIVE_UNSLOP_CANDIDATES if path.is_file()), None)


def check_drift(live_path=None):
    """Compare the vendored vocabulary against the live user-local unslop skill.

    The live file is machine-specific and absent in CI, so its absence is a skip and never
    a failure. Same contract as check_global_rules_mirror_drift in tools/verify_skills.py.

    live_path lets a caller supply the live source instead of discovering it. The tests that
    prove this gate rejects drift need one, because on a machine with no installed unslop
    the skip above returns 0 before any comparison happens, and a mutation test asserting
    failure would fail for the wrong reason.
    """
    live_path = live_path or find_live_unslop()
    if live_path is None or not live_path.is_file():
        print("drift check skipped, no installed unslop at "
              + (str(live_path) if live_path
                 else " or ".join(str(p) for p in LIVE_UNSLOP_CANDIDATES)))
        return 0
    live = extract_live_vocabulary(live_path.read_text())
    if live is None:
        print(f"drift check FAILED to parse a plausible rule 7 out of {live_path}. Either "
              f"the rule moved or the regex clipped its list; either way the vendored list "
              f"may be stale and this check can no longer tell.", file=sys.stderr)
        return 1

    spec = json.loads(RULES_FILE.read_text())
    snapshot = {term.lower() for term in spec["live_rule_7_snapshot"]["terms"]}
    # Both directions against the snapshot. Comparing only live-minus-vendored misses a term
    # the live skill removed, which stays vendored and keeps scoring text the rule no longer
    # calls a tell. The union of all vendored terms cannot serve as the yardstick, because
    # the other rules deliberately carry terms rule 7 never listed.
    added = sorted(live - snapshot)
    removed = sorted(snapshot - live)
    print(f"live rule 7 lists {len(live)} terms; the vendored snapshot holds {len(snapshot)}")

    failed = False
    if added:
        print(f"added to the live rule since vendoring: {', '.join(added)}")
        failed = True
    if removed:
        print(f"removed from the live rule but still vendored: {', '.join(removed)}")
        failed = True

    # A snapshot term still has to be counted by some rule. unslop files `landscape` under
    # rule 7 and this scorer counts it under rule 26, so the coverage question is answered
    # against every vendored rule rather than per rule.
    vendored = {term.lower() for rule in spec["rules"] for term in rule.get("terms", [])}
    uncovered = sorted(snapshot - vendored)
    if uncovered:
        print(f"in the snapshot but counted by no vendored rule: {', '.join(uncovered)}")
        failed = True

    if failed:
        print("update slop_rules.json, then re-snapshot live_rule_7_snapshot", file=sys.stderr)
        return 1
    print("live rule 7 matches the vendored snapshot, and every term is counted")
    return 0


def format_report(label, result):
    lines = [f"{label}",
             f"  {result['words']} words, {result['sentences']} sentences, "
             f"{result['tells_per_100w']} tells per 100 words"]
    fired = {n: h for n, h in result["rules"].items() if h["count"]}
    for name, hit in sorted(fired.items(), key=lambda kv: -kv[1]["count"]):
        lines.append(f"    {name:<26} {hit['count']:>4}  ({hit['per_100w']} /100w)")
    if not fired:
        lines.append("    no countable tells")
    measures = result["measures"]
    lines.append(f"  sentence words: mean {measures['mean_sentence_words']}, "
                 f"stdev {measures['sentence_words_stdev']}, "
                 f"{measures['pct_sentences_over_35w']}% over {LONG_SENTENCE_WORDS}")
    lines.append(f"  adverbs {measures['adverb_per_100w']} /100w, "
                 f"nominalisations {measures['nominalisation_per_100w']} /100w")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", type=pathlib.Path)
    parser.add_argument("--json", action="store_true", help="emit machine-readable scores")
    parser.add_argument("--check-drift", action="store_true",
                        help="compare the vendored rule list against the live unslop skill")
    args = parser.parse_args()

    if args.check_drift:
        return check_drift()
    if not args.files:
        parser.error("give at least one file, or --check-drift")

    rules, measures = load_rules()
    results = {}
    for path in args.files:
        if not path.is_file():
            print(f"missing file: {path}", file=sys.stderr)
            return 2
        results[str(path)] = score(path.read_text(), rules, measures)

    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    for label, result in results.items():
        print(format_report(label, result))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
