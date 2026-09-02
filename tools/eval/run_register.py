#!/usr/bin/env python3
"""Register eval: does the prose a skill is written in change the prose the model emits?

That is the open half of issue #37. The punctuation half is settled and provable. This
measures the other half so a 90,000-word rewrite can be costed against a number instead of
an assertion.

Each case asks a skill for a text artifact a human reads, then scores it with
slop_score.py. Run it without --variant to establish how much the score moves between
identical runs; that spread is the noise floor, and a rewrite has to beat it to mean
anything. Run it with --variant pointing at a modified skills tree to get the delta.

One confound this cannot remove and therefore reports: a standing instruction in the user's
global CLAUDE.md fires the `unslop` skill in every session, which cleans the output on its
way out no matter what the skill under test looks like. Every run records whether it fired.
If it fired in both arms and the delta is flat, the honest reading is that the global rule
already does this job and the rewrite buys nothing measurable.

    python3 tools/eval/run_register.py --case pr-body --repeat 5
    python3 tools/eval/run_register.py --case pr-body --repeat 3 --variant ../rewritten/skills
"""
import argparse
import datetime
import json
import pathlib
import shutil
import statistics
import re
import subprocess
import sys
import tempfile
import uuid

import harness
import slop_score

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
CASES = HERE / "register_cases.json"
FIXTURE = HERE / "fixture"
SKILLS = REPO / "skills"

# No Bash. Every artifact here is a draft, and a run that cannot shell out cannot open a
# PR, file an issue, or push. The diff each case needs is in its prompt instead.
CASE_TOOLS = ["Skill", "Read", "Glob", "Grep"]

# Below this, a per-100-word rate is arithmetic on noise: one stray tell in a 20-word answer
# reads as 5.0, above the whole observed baseline. A reply that is only a fenced code block
# scores a flawless zero on every metric and drags its arm toward a false improvement.
MIN_SCORABLE_WORDS = 80

TRACKED_MEASURES = ["tells_per_100w", "nominalisation_per_100w", "adverb_per_100w",
                    "sentence_words_stdev", "mean_sentence_words", "pct_sentences_over_35w"]

# One metric decides, the other five describe. Testing all six at a 2-sigma threshold is a
# 24% chance of at least one false "probable" per case under a true null, and across four
# cases the run would more often than not report an effect on an unchanged tree. This is the
# metric issue #37 names ("dense nominalised spec prose") and the tightest in the baseline.
PRIMARY_METRIC = "nominalisation_per_100w"

# Two-sided 95% critical values of t by degrees of freedom. With n=3 per arm the spread is
# estimated from 3 points and df=4, where the real threshold is 2.776 rather than 2.0, so
# reading sigma against a normal would call p=0.12 "probable".
T_CRITICAL_95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
                 8: 2.306, 9: 2.262, 10: 2.228, 12: 2.179, 15: 2.131, 20: 2.086, 30: 2.042}


def t_critical(degrees_of_freedom):
    """Nearest tabulated two-sided 95% t value, falling back to the normal limit."""
    if degrees_of_freedom < 1:
        return None
    for df in sorted(T_CRITICAL_95):
        if degrees_of_freedom <= df:
            return T_CRITICAL_95[df]
    return 1.96


def flatten(scored):
    """One flat dict of the numbers worth comparing across runs."""
    flat = {"tells_per_100w": scored["tells_per_100w"]}
    flat.update(scored["measures"])
    flat["words"] = scored["words"]
    return flat


def failed_skill_load(tool_calls, slug):
    """Why the skill under test is not usable evidence, or None when it loaded.

    A Skill tool_use proves the agent asked for the skill, not that it got it. If the
    sandbox copy fails to register, the call comes back "skill not found", the agent writes
    a perfectly good answer from base-model knowledge, and the run scores the base model in
    both arms. That is a null result the numbers cannot distinguish from a real one.
    """
    named = sorted({(c["input"] or {}).get("skill") for c in tool_calls
                    if c["name"] == "Skill"} - {None})
    calls = [call for call in tool_calls
             if call["name"] == "Skill" and (call["input"] or {}).get("skill") == slug]
    if not calls:
        return f"{slug} never fired (fired: {', '.join(named) or 'nothing'})"
    # The rename stops the installed copy from *shadowing* the sandbox one, not from also
    # loading. The installed `done` says it is mandatory before reporting any task complete,
    # so it can fire alongside `done-under-test` and put prose into the answer that is
    # byte-identical in both arms, shrinking the delta toward zero.
    original = slug.removesuffix("-under-test")
    if original in named:
        return f"the installed {original} loaded alongside {slug}, so both arms share prose"
    if all(re.search(r"not found|no such skill|unknown skill|error", call["result"],
                     re.IGNORECASE)
           for call in calls if call["result"]):
        if any(call["result"] for call in calls):
            return f"{slug} was invoked but did not load: {calls[0]['result'][:120]}"
    return None


def stage_under_unique_name(skill_dir, slug, into):
    """Copy a skill out under a name nothing else can claim, and return the new path.

    Every skill these cases exercise is also installed in ~/.claude/skills and
    ~/.agents/skills. A project copy sharing that name competes with the installed one, and
    if the installed copy wins then both arms of an A/B run load identical prose, every
    delta is zero by construction, and the run reports a null result that means nothing.
    Renaming the slug removes the question instead of answering it.
    """
    staged = into / slug
    shutil.copytree(skill_dir, staged)
    skill_md = staged / "SKILL.md"
    text = skill_md.read_text()
    patched, count = re.subn(r"(?m)^name:[ \t]*\S+[ \t]*$", f"name: {slug}", text, count=1)
    if count != 1:
        raise ValueError(f"{skill_md} has no frontmatter `name:` line to rewrite; the "
                         f"injected copy would collide with the installed one")
    skill_md.write_text(patched)
    return staged


def run_once(case, skills_root, budget, timeout):
    """Return (scored_or_None, final_text, ambient_skills, error)."""
    skill_dir = skills_root / case["skill"]
    if not (skill_dir / "SKILL.md").is_file():
        return None, "", [], f"no SKILL.md at {skill_dir}"

    slug = f"{case['skill']}-under-test"
    staging = pathlib.Path(tempfile.mkdtemp(prefix="register-stage-"))
    temp_root = None
    try:
        staged_skill = stage_under_unique_name(skill_dir, slug, staging)
        temp_root, repo = harness.make_sandbox(
            "register-eval-", FIXTURE, skills=[staged_skill])
    except (ValueError, OSError, RuntimeError) as error:
        # Sandbox setup fails for ordinary reasons: a signing hook, a full disk, a bad
        # global git config. Letting it escape kills every remaining case and loses the
        # arm's collected results, because the summary is only written at case end.
        if temp_root:
            shutil.rmtree(temp_root, ignore_errors=True)
        return None, "", [], f"sandbox setup failed: {error}"
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    prompt = case["prompt"].replace("$SKILL_UNDER_TEST", f"${slug}")
    command = [
        "claude", "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "dontAsk",
        "--tools", ",".join(CASE_TOOLS),
        "--allowedTools", ",".join(CASE_TOOLS),
        "--max-budget-usd", str(budget),
    ]
    process = None
    try:
        process = subprocess.Popen(
            command, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as expiry:
            timed_out = True
            partial = expiry.stdout
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            stdout, stderr = harness.kill_process_group(process, partial or "")

        final_text, tool_calls, result_error = harness.parse_transcript(stdout)
        ambient = [name
                   for event in harness.iter_events(stdout)
                   for name in harness.parse_skill_names(event)]
        # A cut-off run holds a draft, not an answer, and a draft is short and unfinished in
        # exactly the direction that reads as cleaner prose. Scoring one biases the arm it
        # lands in toward a false improvement.
        if timed_out:
            return None, final_text, ambient, f"timeout after {timeout}s"
        if result_error:
            return None, final_text, ambient, result_error
        if process.returncode != 0:
            detail = (stderr or "").strip().replace("\n", " ")[:160]
            return None, final_text, ambient, f"claude exited {process.returncode}: {detail}"
        if not final_text.strip():
            return None, "", ambient, "empty transcript"
        # A run where the skill never loaded scores the base model, not the skill. Counting
        # it would put the thing being measured into the noise and quietly flatten every
        # delta toward zero, which is the one failure this eval must not have. The tool_use
        # block only proves the call was made, so the result it returned decides.
        skill_error = failed_skill_load(tool_calls, slug)
        if skill_error:
            return None, final_text, ambient, skill_error
        scored = slop_score.score(final_text)
        floor = case.get("min_words", MIN_SCORABLE_WORDS)
        if scored["words"] < floor:
            return None, final_text, ambient, (
                f"only {scored['words']} prose words after stripping code, "
                f"under this case's floor of {floor} for a per-100-word rate")
        return scored, final_text, ambient, None
    finally:
        if process is not None:
            harness.kill_process_group(process)
        shutil.rmtree(temp_root, ignore_errors=True)


def summarise(runs):
    """Mean and spread per metric across repeated runs of one arm."""
    if not runs:
        return {}
    out = {}
    for metric in TRACKED_MEASURES:
        values = [flatten(r)[metric] for r in runs]
        # Unrounded on purpose. difference_sigma divides by these, and rounding a stdev of
        # 0.34 to 2dp is up to 1.5% error in sigma, enough to move a result across the
        # threshold that decides whether a rewrite goes ahead. Rounding happens at print.
        out[metric] = {
            "mean": statistics.fmean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }
    return out


def print_arm(label, stats, runs):
    print(f"\n{label}  (n={len(runs)})")
    if not stats:
        print("  no successful runs")
        return
    print(f"  {'metric':<26} {'mean':>8} {'stdev':>8} {'min':>8} {'max':>8}")
    for metric in TRACKED_MEASURES:
        row = stats[metric]
        print(f"  {metric:<26} {row['mean']:>8.2f} {row['stdev']:>8.2f} "
              f"{row['min']:>8.2f} {row['max']:>8.2f}")


def difference_sigma(baseline, variant, n_baseline, n_variant):
    """How many standard errors separate the two arms' means, or None if it cannot be said.

    The yardstick is the standard error of the difference, not either arm's raw standard
    deviation. For equal arms SE_diff is s*sqrt(2/n), so the raw spread is sqrt(n/2) times
    too strict: 1.58x at n=5, and enough to report a real effect as noise.
    """
    change = variant["mean"] - baseline["mean"]
    if n_baseline < 2 or n_variant < 2:
        return change, None, "need 2+ scored runs per arm"
    pooled = (baseline["stdev"] ** 2 / n_baseline + variant["stdev"] ** 2 / n_variant) ** 0.5
    # Zero pooled variance and too few runs are different diagnoses. Reporting both as a
    # sample-size problem points the operator at the wrong fix when the real cause is that
    # every run collapsed to the same value, usually because none of them scored anything.
    if pooled == 0:
        return change, None, "no variance in either arm, check the scored runs"
    return change, change / pooled, None


def print_delta(baseline_stats, variant_stats, n_baseline, n_variant):
    threshold = t_critical(n_baseline + n_variant - 2)
    print(f"\ndelta (variant minus baseline). sigma is the difference over its standard "
          f"error.\nOnly {PRIMARY_METRIC} decides; the rest describe. Threshold |t| >= "
          f"{threshold} at 95% for n={n_baseline}+{n_variant}.")
    print(f"  {'metric':<26} {'delta':>8} {'sigma':>8}   reading")
    for metric in TRACKED_MEASURES:
        change, sigma, why = difference_sigma(
            baseline_stats[metric], variant_stats[metric], n_baseline, n_variant)
        role = "decides" if metric == PRIMARY_METRIC else "describes"
        if sigma is None:
            print(f"  {metric:<26} {change:>+8.2f} {'n/a':>8}   {why} [{role}]")
            continue
        if abs(sigma) >= threshold:
            reading = "significant at 95%"
        elif abs(sigma) >= 1:
            reading = "suggestive, underpowered"
        else:
            reading = "indistinguishable from noise"
        print(f"  {metric:<26} {change:>+8.2f} {sigma:>+8.2f}   {reading} [{role}]")
    print(f"\n  Read the [decides] row alone as the result. The [describes] rows are "
          f"context;\n  treating any of them as a finding is how six tests become one "
          f"false positive.")


def print_sensitivity(stats, n):
    """What size of change this many runs could actually detect, per metric.

    Printed with the baseline because it is the number that decides whether a rewrite is
    worth attempting. A metric whose minimum detectable effect is larger than any plausible
    rewrite is not evidence, and running the variant arm against it only buys a false null.
    """
    print(f"\n  smallest change {n} runs per arm could call at 2 sigma")
    print(f"  {'metric':<26} {'absolute':>10} {'relative':>10}")
    for metric in TRACKED_MEASURES:
        row = stats[metric]
        if n < 2 or row["mean"] == 0:
            continue
        detectable = 2 * ((2 * row["stdev"] ** 2 / n) ** 0.5)
        print(f"  {metric:<26} {detectable:>10.2f} {100 * detectable / row['mean']:>9.0f}%")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", help="run one case by id (default: all)")
    parser.add_argument("--repeat", type=int, default=3,
                        help="runs per arm. Output is non-deterministic, so a single run "
                             "reports a coin flip as a fact. 5+ before acting on a delta.")
    parser.add_argument("--variant", type=pathlib.Path,
                        help="a second skills/ tree to compare against the committed one")
    parser.add_argument("--budget", type=float, default=2.50,
                        help="per-run USD cap. These skills are large and load references, "
                             "so a run capped at 1.00 dies at the result event with the "
                             "artifact already written, which reads as an error.")
    parser.add_argument("--timeout", type=int, default=300, help="per-run seconds")
    parser.add_argument("--output-dir", type=pathlib.Path)
    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    variant_root = args.variant.resolve() if args.variant else None
    if variant_root and not variant_root.is_dir():
        parser.error(f"variant tree is not a directory: {variant_root}")

    cases = json.loads(CASES.read_text())["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            parser.error(f"unknown case: {args.case}")

    run_id = (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
              + "-" + uuid.uuid4().hex[:8])
    output_dir = args.output_dir or REPO / ".eval-results" / "register" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    arms = [("baseline", SKILLS)]
    if variant_root:
        arms.append(("variant", variant_root))

    exit_code = 0
    for case in cases:
        print(f"\n{'=' * 72}\n{case['id']}  ({case['skill']} -> {case['artifact']})")
        print(f"{'=' * 72}")
        stats_by_arm, runs_by_arm, audit_by_arm = {}, {}, {}
        for arm_name, root in arms:
            runs, ambient_hits, failures = [], 0, []
            for index in range(args.repeat):
                print(f"  {arm_name} {index + 1}/{args.repeat} ... ", end="", flush=True)
                scored, text, ambient, error = run_once(
                    case, root, args.budget, args.timeout)
                stem = f"{case['id']}.{arm_name}.{index + 1}"
                if text:
                    (output_dir / f"{stem}.md").write_text(text)
                if error:
                    failures.append(error)
                    print(f"ERROR {error[:60]}")
                    continue
                (output_dir / f"{stem}.score.json").write_text(
                    json.dumps(scored, indent=2) + "\n")
                runs.append(scored)
                if "unslop" in ambient:
                    ambient_hits += 1
                print(f"{scored['words']:>4}w  "
                      f"{scored['tells_per_100w']:>5} tells/100w")
            if failures:
                exit_code = 1
            stats_by_arm[arm_name] = summarise(runs)
            runs_by_arm[arm_name] = runs
            # Dropped runs are not random: if one arm errors more often, its survivors are a
            # biased sample. A mean with no run count beside it hides that completely.
            audit_by_arm[arm_name] = {
                "requested": args.repeat,
                "scored": len(runs),
                "failed": len(failures),
                "failures": failures,
                "unslop_fired": ambient_hits,
                "stats": stats_by_arm[arm_name],
            }
            print_arm(arm_name, stats_by_arm[arm_name], runs)
            print(f"  {len(runs)}/{args.repeat} runs scored"
                  + (f", {len(failures)} failed" if failures else ""))
            if runs:
                print(f"  unslop fired in {ambient_hits}/{len(runs)} scored runs")
            for failure in failures:
                print(f"    failed: {failure}")
            if arm_name == "baseline" and len(runs) > 1:
                print_sensitivity(stats_by_arm[arm_name], len(runs))

        if variant_root and runs_by_arm["baseline"] and runs_by_arm["variant"]:
            print_delta(stats_by_arm["baseline"], stats_by_arm["variant"],
                        len(runs_by_arm["baseline"]), len(runs_by_arm["variant"]))

        (output_dir / f"{case['id']}.summary.json").write_text(
            json.dumps(audit_by_arm, indent=2) + "\n")

    print(f"\nRaw results: {output_dir}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
