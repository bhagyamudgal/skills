#!/usr/bin/env python3
"""Register eval: does the prose a skill is written in change the prose the model emits?

That is the open half of issue #37. The punctuation half is settled and provable. This
measures the other half so a 90,000-word rewrite can be costed against a number instead of
an assertion.

Each case asks a skill for a text artifact a human reads, then scores it with
slop_score.py. Run it without --variant to establish how much the score moves between
identical runs; that spread is the noise floor, and a rewrite has to beat it to mean
anything. Run it with --variant pointing at a modified skills tree to get the delta. The
runner can be Claude or Codex, but results from different runners are separate experiments.

One confound this cannot remove is the runner's ambient instructions. Claude receives the
user's global CLAUDE.md. Codex runs without mutable user config or the user's global
AGENTS.md, but still receives version-bundled instructions and the installed skill catalog.
Those rules constrain prose before the staged skill is consulted. Read the baseline as a
floor the runner environment imposes, not as what the skill produces on its own. A flat
delta means the staged rewrite added no measurable effect in that environment.

    python3 tools/eval/run_register.py --case pr-body --repeat 5
    python3 tools/eval/run_register.py --runner codex --model gpt-5.6-sol \
        --case pr-body --repeat 3 --variant ../rewritten/skills
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import random
import re
import shutil
import statistics
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

CASE_TOOLS = ["Skill", "Read", "Glob", "Grep"]
RUNNERS = ("claude", "codex")
SUPPORTED_CODEX_VERSION = "codex-cli 0.152.1"
CODEX_REASONING_EFFORT = "high"
CODEX_SANDBOX_MODE = "read-only"
RUNNER_VERSION_TIMEOUT_SECONDS = 30
PROTOCOL_FILES = (
    ("tools/eval/run_register.py", pathlib.Path(__file__).resolve()),
    ("tools/eval/harness.py", HERE / "harness.py"),
    ("tools/eval/slop_score.py", HERE / "slop_score.py"),
    ("tools/eval/slop_rules.json", HERE / "slop_rules.json"),
)

# Below this a per-100-word rate is arithmetic on noise, and a code-block-only reply scores
# a flawless zero on every metric.
MIN_SCORABLE_WORDS = 80

TRACKED_MEASURES = ["tells_per_100w", "nominalisation_per_100w", "adverb_per_100w",
                    "sentence_words_stdev", "mean_sentence_words", "pct_sentences_over_35w"]

# One metric decides, the rest describe: six tested at 2 sigma is a 24% false-positive rate
# per case. This is the one issue #37 names and the tightest in the baseline.
PRIMARY_METRIC = "nominalisation_per_100w"

# Two-sided 95% t by degrees of freedom. At n=3 per arm df=4 and the threshold is 2.776, so
# reading sigma against a normal would call p=0.12 significant.
T_CRITICAL_95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
                 8: 2.306, 9: 2.262, 10: 2.228, 12: 2.179, 15: 2.131, 20: 2.086, 30: 2.042,
                 40: 2.021, 60: 2.000, 120: 1.980}

def t_critical(degrees_of_freedom):
    """Two-sided 95% t, rounding down to the nearest tabulated row.

    Rounding down keeps the table conservative. Picking the next row up returns a smaller
    critical value than the true df warrants, which is the direction that invents
    significance.

    There is deliberately no normal-limit fallback. 1.960 is the df=infinity value and every
    finite df sits above it, so switching to it past the table hands out a threshold below
    the true cutoff. Welch degrees of freedom are fractional, so df=120.1 is reachable.
    Holding the df=120 row for anything larger stays conservative at every finite df.
    """
    if degrees_of_freedom < 1:
        return None
    tabulated = [df for df in sorted(T_CRITICAL_95) if df <= degrees_of_freedom]
    if not tabulated:
        return T_CRITICAL_95[min(T_CRITICAL_95)]
    return T_CRITICAL_95[max(tabulated)]


def welch_degrees_of_freedom(baseline, variant, n_baseline, n_variant):
    """Welch-Satterthwaite df, which is what the unpooled standard error requires.

    Pairing that error with the pooled n1+n2-2 assumes equal variances. When one arm is
    noisier the pooled df is far too generous: at a 20x variance ratio and 3 runs an arm it
    returns df=4 and a 2.776 threshold where Welch gives df=2 and demands 4.303, so a result
    that is not significant prints as significant.
    """
    baseline_term = baseline["stdev"] ** 2 / n_baseline
    variant_term = variant["stdev"] ** 2 / n_variant
    denominator = (baseline_term ** 2 / (n_baseline - 1)
                   + variant_term ** 2 / (n_variant - 1))
    if denominator == 0:
        return None
    return (baseline_term + variant_term) ** 2 / denominator


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
    # The rename stops the installed copy shadowing the sandbox one, not from also loading
    # alongside it and putting prose byte-identical in both arms into the answer.
    original = slug.removesuffix("-under-test")
    if original in named:
        return f"the installed {original} loaded alongside {slug}, so both arms share prose"
    if all(re.search(r"not found|no such skill|unknown skill|error", call["result"],
                     re.IGNORECASE)
           for call in calls if call["result"]):
        if any(call["result"] for call in calls):
            return f"{slug} was invoked but did not load: {calls[0]['result'][:120]}"
    return None


def stage_under_unique_name(skill_dir, slug, into, canary=None):
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
    if canary:
        patched = (f"{patched.rstrip()}\n\nFor this evaluation only, append the exact marker "
                   f"`{canary}` on its own line after the requested artifact.\n")
    skill_md.write_text(patched)
    return staged


def build_codex_command(prompt, skill_name, model):
    installed_skill = pathlib.Path.home() / ".agents" / "skills" / skill_name / "SKILL.md"
    skill_override = (
        f"skills.config=[{{path={json.dumps(str(installed_skill))},enabled=false}}]"
    )
    reasoning_override = f"model_reasoning_effort={json.dumps(CODEX_REASONING_EFFORT)}"
    return [
        "codex", "exec", "--ephemeral", "--json", "--sandbox", CODEX_SANDBOX_MODE,
        "--ignore-user-config", "--model", model, "--config", reasoning_override,
        "--config", skill_override, prompt,
    ]


def create_codex_environment(temp_root):
    source_home = pathlib.Path(
        os.environ.get("CODEX_HOME", pathlib.Path.home() / ".codex"))
    source_auth = source_home / "auth.json"
    if not source_auth.is_file():
        raise FileNotFoundError(f"Codex auth file not found: {source_auth}")
    isolated_home = pathlib.Path(temp_root) / ".codex-home"
    isolated_home.mkdir()
    (isolated_home / "auth.json").symlink_to(source_auth)
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(isolated_home)
    return environment


def validate_codex_skill_catalog(repo, original, staged, skill_override, timeout,
                                 environment=None, model=None):
    reasoning_override = f"model_reasoning_effort={json.dumps(CODEX_REASONING_EFFORT)}"
    sandbox_override = f"sandbox_mode={json.dumps(CODEX_SANDBOX_MODE)}"
    command = ["codex", "debug", "prompt-input"]
    if model:
        command.extend(("--config", f"model={json.dumps(model)}"))
    command.extend(("--config", sandbox_override, "--config", reasoning_override,
                    "--config", skill_override, "probe"))
    try:
        completed = subprocess.run(
            command,
            cwd=repo, capture_output=True, text=True, timeout=timeout,
            env=environment)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"could not inspect Codex skill catalog: {error}"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip().replace("\n", " ")[:160]
        return None, f"Codex skill catalog inspection failed: {detail}"
    try:
        messages = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None, "Codex skill catalog inspection returned malformed JSON"
    if not isinstance(messages, list):
        return None, "Codex skill catalog inspection returned a non-list prompt"
    catalogs = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "input_text":
                continue
            text = block.get("text")
            if isinstance(text, str) and "<skills_instructions>" in text:
                catalogs.append(text)
    if len(catalogs) != 1:
        return None, f"Codex prompt contained {len(catalogs)} skill catalogs instead of one"
    original_count = len(re.findall(rf"(?m)^- {re.escape(original)}:", catalogs[0]))
    staged_count = len(re.findall(rf"(?m)^- {re.escape(staged)}:", catalogs[0]))
    if original_count:
        return None, f"installed skill {original} remained visible in the Codex catalog"
    if staged_count != 1:
        return None, f"staged skill {staged} appeared {staged_count} times instead of once"
    visible_messages = []
    for message in messages:
        role = message.get("role") if isinstance(message, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(role, str) or not isinstance(content, list):
            return None, "Codex prompt contained a malformed model-visible message"
        visible_messages.append({"role": role, "content": content})
    serialized = json.dumps(visible_messages, sort_keys=True, separators=(",", ":"))
    locations = [repo]
    if environment and environment.get("CODEX_HOME"):
        locations.append(pathlib.Path(environment["CODEX_HOME"]))
    for location in locations:
        serialized = serialized.replace(str(location), "<runtime-root>")
        serialized = serialized.replace(str(location.resolve()), "<runtime-root>")
    serialized = re.sub(
        rf"- {re.escape(staged)}:.*?(?=\\n)",
        "- <staged-skill>: <arm-skill>", serialized)
    return hashlib.sha256(serialized.encode()).hexdigest(), None


def build_arm_schedule(arms, repeat, seed):
    generator = random.Random(seed)
    schedule = []
    for pair_index in range(repeat):
        pair = list(arms)
        generator.shuffle(pair)
        schedule.extend((arm_name, root, pair_index) for arm_name, root in pair)
    return schedule


def skill_directory_digest(skill_dir):
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in skill_dir.rglob("*") if candidate.is_file()):
        digest.update(path.relative_to(skill_dir).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def protocol_sources(fixture=None):
    if fixture is None:
        fixture = FIXTURE
    sources = list(PROTOCOL_FILES)
    sources.append(("tools/eval/register_cases.json", CASES))
    for source in sorted(path for path in fixture.rglob("*") if path.is_file()):
        relative = source.relative_to(fixture).as_posix()
        sources.append((f"tools/eval/fixture/{relative}", source))
    return tuple(sources)


def protocol_digest(sources=None):
    if sources is None:
        sources = protocol_sources()
    digest = hashlib.sha256()
    for name, source in sorted(sources):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(source if isinstance(source, bytes) else source.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def snapshot_arm_roots(arms, skill_name):
    snapshot = tempfile.TemporaryDirectory(prefix="register-protocol-")
    snapshot_root = pathlib.Path(snapshot.name)
    frozen_arms = []
    digests = {}
    try:
        for arm_name, source_root in arms:
            source = source_root / skill_name
            if not (source / "SKILL.md").is_file():
                raise ValueError(f"no SKILL.md at {source}")
            frozen_root = snapshot_root / arm_name
            shutil.copytree(source, frozen_root / skill_name)
            frozen_arms.append((arm_name, frozen_root))
            digests[arm_name] = skill_directory_digest(frozen_root / skill_name)
    except Exception:
        snapshot.cleanup()
        raise
    return snapshot, frozen_arms, digests


def parse_codex_transcript(output):
    final_text = ""
    result_error = None
    warnings = []
    saw_thread = False
    saw_turn = False
    terminal_event = None
    for line_number, line in enumerate(output.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return final_text, f"malformed JSONL at line {line_number}"
        if not isinstance(event, dict):
            return final_text, f"non-object JSONL event at line {line_number}"
        event_type = event.get("type")
        if terminal_event is not None:
            return final_text, f"{event_type or 'unknown event'} appeared after terminal event"
        item = event.get("item") or {}
        if not isinstance(item, dict):
            return final_text, f"non-object item at line {line_number}"
        if event_type == "thread.started":
            if saw_thread or saw_turn:
                return final_text, "duplicate or late thread.started event"
            saw_thread = True
        elif event_type == "turn.started":
            if not saw_thread or saw_turn:
                return final_text, "turn.started appeared without one preceding thread.started"
            saw_turn = True
        elif event_type in ("item.started", "item.completed"):
            item_type = item.get("type")
            if item_type == "reasoning":
                continue
            if event_type == "item.completed" and item_type == "agent_message":
                if not saw_turn:
                    return final_text, "agent message appeared before turn.started"
                final_text = item.get("text", "")
            elif event_type == "item.completed" and item_type == "error":
                detail = str(item.get("message", "")).strip().replace("\n", " ")[:160]
                result_error = detail or "Codex emitted an error item"
            else:
                result_error = f"Codex emitted disallowed {item_type or 'unknown'} item"
        elif event_type == "turn.completed":
            terminal_event = event_type
            if not saw_turn:
                result_error = "turn.completed appeared before turn.started"
            elif not final_text.strip():
                result_error = "completed turn has no final agent message"
        elif event_type == "turn.failed":
            terminal_event = event_type
            detail = event.get("error") or event.get("message") or event
            if isinstance(detail, dict):
                detail = detail.get("message") or json.dumps(detail)
            result_error = str(detail).strip().replace("\n", " ")[:160]
        elif event_type == "error":
            detail = event.get("message") or event.get("error") or event
            if isinstance(detail, dict):
                detail = detail.get("message") or json.dumps(detail)
            warnings.append(str(detail).strip().replace("\n", " ")[:160])
        else:
            result_error = f"Codex emitted unknown {event_type or 'missing-type'} event"
    if not saw_thread:
        return final_text, "missing thread.started event, transcript truncated"
    if not saw_turn:
        return final_text, "missing turn.started event, transcript truncated"
    if terminal_event is None:
        detail = f": {warnings[-1]}" if warnings else ""
        return final_text, f"missing terminal event, transcript truncated{detail}"
    return final_text, result_error


def validate_codex_canary(text, marker):
    count = text.count(marker)
    if count != 1:
        return text, f"Codex skill canary appeared {count} times instead of once"
    return text.replace(marker, "").strip(), None


def run_once(case, skills_root, budget, timeout, runner="claude", model=None,
             scoring_rules=None, scoring_measures=None, fixture=FIXTURE):
    """Return (scored_or_None, final_text, ambient_skills, context_digest, error)."""
    skill_dir = skills_root / case["skill"]
    if not (skill_dir / "SKILL.md").is_file():
        return None, "", [], None, f"no SKILL.md at {skill_dir}"
    if runner == "codex" and not model:
        return None, "", [], None, "Codex runs require an explicit model"

    slug = f"{case['skill']}-under-test"
    canary = f"<!-- register-skill-loaded:{slug} -->" if runner == "codex" else None
    staging = pathlib.Path(tempfile.mkdtemp(prefix="register-stage-"))
    temp_root = None
    try:
        staged_skill = stage_under_unique_name(skill_dir, slug, staging, canary=canary)
        temp_root, repo = harness.make_sandbox(
            "register-eval-", fixture, skills=[staged_skill],
            skill_directory=".agents/skills" if runner == "codex" else ".claude/skills")
    except (ValueError, OSError, RuntimeError) as error:
        # Escaping here kills every remaining case and loses the arm, since the summary is
        # only written at case end.
        if temp_root:
            shutil.rmtree(temp_root, ignore_errors=True)
        return None, "", [], None, f"sandbox setup failed: {error}"
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    process = None
    try:
        prompt = case["prompt"].replace("$SKILL_UNDER_TEST", f"${slug}")
        context_digest = None
        environment = None
        if runner == "codex":
            try:
                environment = create_codex_environment(temp_root)
            except OSError as error:
                return None, "", [], None, f"could not isolate Codex configuration: {error}"
            command = build_codex_command(prompt, case["skill"], model)
            skill_override = command[-2]
            context_digest, catalog_error = validate_codex_skill_catalog(
                repo, case["skill"], slug, skill_override, timeout, environment, model)
            if catalog_error:
                return None, "", [], None, catalog_error
        else:
            command = [
                "claude", "-p", prompt,
                "--output-format", "stream-json", "--verbose",
                "--permission-mode", "dontAsk",
                "--tools", ",".join(CASE_TOOLS),
                "--allowedTools", ",".join(CASE_TOOLS),
                "--max-budget-usd", str(budget),
            ]
        process = subprocess.Popen(
            command, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True, env=environment)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as expiry:
            timed_out = True
            partial = expiry.stdout
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            stdout, stderr = harness.kill_process_group(process, partial or "")

        if runner == "codex":
            final_text, result_error = parse_codex_transcript(stdout)
            tool_calls = []
            ambient = []
        else:
            final_text, tool_calls, result_error = harness.parse_transcript(stdout)
            ambient = [name
                       for event in harness.iter_events(stdout)
                       for name in harness.parse_skill_names(event)]
        if timed_out:
            return None, final_text, ambient, context_digest, f"timeout after {timeout}s"
        if process.returncode != 0 and not stdout.strip():
            detail = (stderr or "").strip().replace("\n", " ")[:160]
            return (None, final_text, ambient, context_digest,
                    f"{runner} exited {process.returncode}: {detail}")
        if result_error:
            return None, final_text, ambient, context_digest, result_error
        if process.returncode != 0:
            detail = (stderr or "").strip().replace("\n", " ")[:160]
            return (None, final_text, ambient, context_digest,
                    f"{runner} exited {process.returncode}: {detail}")
        if not final_text.strip():
            return None, "", ambient, context_digest, "empty transcript"
        if runner == "codex":
            final_text, skill_error = validate_codex_canary(final_text, canary)
        else:
            skill_error = failed_skill_load(tool_calls, slug)
        if skill_error:
            return None, final_text, ambient, context_digest, skill_error
        scored = slop_score.score(final_text, scoring_rules, scoring_measures)
        floor = case.get("min_words", MIN_SCORABLE_WORDS)
        if scored["words"] < floor:
            return None, final_text, ambient, context_digest, (
                f"only {scored['words']} prose words after stripping code, "
                f"under this case's floor of {floor} for a per-100-word rate")
        ceiling = case.get("max_words")
        if ceiling is not None and scored["words"] > ceiling:
            return None, final_text, ambient, context_digest, (
                f"{scored['words']} prose words after stripping code, over this case's "
                f"ceiling of {ceiling}")
        return scored, final_text, ambient, context_digest, None
    finally:
        try:
            if process is not None:
                harness.kill_process_group(process)
        finally:
            shutil.rmtree(temp_root)


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
        return change, None, None, "need 2+ scored runs per arm"
    unpooled = (baseline["stdev"] ** 2 / n_baseline
                + variant["stdev"] ** 2 / n_variant) ** 0.5
    # Zero variance and too few runs are different diagnoses. Reporting both as a sample-size
    # problem points the operator at the wrong fix when the real cause is that every run
    # collapsed to the same value, usually because none of them scored anything.
    if unpooled == 0:
        return change, None, None, "no variance in either arm, check the scored runs"
    degrees = welch_degrees_of_freedom(baseline, variant, n_baseline, n_variant)
    return change, change / unpooled, degrees, None


def print_delta(baseline_stats, variant_stats, n_baseline, n_variant):
    # The word floor drops short answers and the budget cap drops long ones, so unequal arms
    # mean any delta may be survivorship rather than effect.
    if n_baseline != n_variant:
        print(f"\n  WARNING: arms are unbalanced, {n_baseline} baseline against "
              f"{n_variant} variant scored runs. Runs are dropped for reasons correlated "
              f"with output length, so treat every row below as unreliable and rerun "
              f"until both arms are equal.")
    print(f"\ndelta (variant minus baseline). sigma is the difference over its standard "
          f"error, judged\nagainst a per-metric Welch threshold. Only {PRIMARY_METRIC} "
          f"decides; the rest describe.")
    print(f"  {'metric':<26} {'delta':>8} {'sigma':>8} {'df':>6} {'t95':>6}   reading")
    decision = None
    for metric in TRACKED_MEASURES:
        change, sigma, degrees, why = difference_sigma(
            baseline_stats[metric], variant_stats[metric], n_baseline, n_variant)
        role = "decides" if metric == PRIMARY_METRIC else "describes"
        if sigma is None:
            print(f"  {metric:<26} {change:>+8.2f} {'n/a':>8} {'':>6} {'':>6}   "
                  f"{why} [{role}]")
            if metric == PRIMARY_METRIC:
                decision = {
                    "metric": metric,
                    "delta": change,
                    "sigma": None,
                    "degrees_of_freedom": None,
                    "threshold_95": None,
                    "reading": why,
                }
            continue
        threshold = t_critical(degrees) if degrees else None
        if threshold is None:
            reading = "cannot set a threshold"
        elif abs(sigma) >= threshold:
            if metric == PRIMARY_METRIC:
                direction = "improvement" if change < 0 else "regression"
                reading = f"significant {direction} at 95%"
            else:
                reading = "significant at 95%"
        elif abs(sigma) >= 1:
            reading = "suggestive, underpowered"
        else:
            reading = "indistinguishable from noise"
        print(f"  {metric:<26} {change:>+8.2f} {sigma:>+8.2f} {degrees:>6.1f} "
              f"{threshold if threshold else 0:>6.3f}   {reading} [{role}]")
        if metric == PRIMARY_METRIC:
            decision = {
                "metric": metric,
                "delta": change,
                "sigma": sigma,
                "degrees_of_freedom": degrees,
                "threshold_95": threshold,
                "reading": reading,
            }
    print("\n  Read the [decides] row alone as the result. The [describes] rows are "
          "context;\n  treating any of them as a finding is how six tests become one "
          "false positive.")
    return decision


def print_sensitivity(stats, n):
    """What size of change this many runs could actually detect, per metric.

    Printed with the baseline because it is the number that decides whether a rewrite is
    worth attempting. A metric whose minimum detectable effect is larger than any plausible
    rewrite is not evidence, and running the variant arm against it only buys a false null.
    """
    # Sized with the same t the verdict uses, not 2 sigma. A 2-sigma table understates the
    # detectable effect against a threshold of 2.306, so a rewrite planned from it comes back
    # "suggestive, underpowered" at exactly the size the table promised was enough.
    threshold = t_critical(2 * n - 2)
    if n < 2 or threshold is None:
        return
    print(f"\n  smallest change {n} runs per arm could call at 95% (t={threshold})")
    print(f"  {'metric':<26} {'absolute':>10} {'relative':>10}")
    for metric in TRACKED_MEASURES:
        row = stats[metric]
        if row["mean"] == 0:
            print(f"  {metric:<26} {'':>10} {'mean is 0':>10}")
            continue
        detectable = threshold * ((2 * row["stdev"] ** 2 / n) ** 0.5)
        print(f"  {metric:<26} {detectable:>10.2f} {100 * detectable / row['mean']:>9.0f}%")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", help="run one case by id (default: all)")
    parser.add_argument("--runner", choices=RUNNERS, default="claude",
                        help="CLI used for every arm; never combine scores across runners")
    parser.add_argument("--model",
                        help="explicit Codex model; required with --runner codex")
    parser.add_argument("--seed", type=int, default=37,
                        help="seed for pair-balanced arm order (default: 37)")
    parser.add_argument("--baseline", type=pathlib.Path,
                        help="baseline skills/ tree (default: this repository's skills/)")
    parser.add_argument("--repeat", type=int, default=3,
                        help="runs per arm. Output is non-deterministic, so a single run "
                             "reports a coin flip as a fact. 5+ before acting on a delta.")
    parser.add_argument("--variant", type=pathlib.Path,
                        help="a second skills/ tree to compare against the committed one")
    parser.add_argument("--budget", type=float, default=2.50,
                        help="Claude per-run USD cap. These skills are large and load references, "
                             "so a run capped at 1.00 dies at the result event with the "
                             "artifact already written, which reads as an error. Ignored "
                             "by Codex.")
    parser.add_argument("--timeout", type=int, default=300, help="per-run seconds")
    parser.add_argument("--output-dir", type=pathlib.Path)
    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    if args.runner == "codex" and not args.model:
        parser.error("--model is required with --runner codex")
    if args.runner == "claude" and args.model:
        parser.error("--model is only valid with --runner codex")
    baseline_root = args.baseline.resolve() if args.baseline else SKILLS
    if not baseline_root.is_dir():
        parser.error(f"baseline tree is not a directory: {baseline_root}")
    variant_root = args.variant.resolve() if args.variant else None
    if variant_root and not variant_root.is_dir():
        parser.error(f"variant tree is not a directory: {variant_root}")

    try:
        version = subprocess.run(
            [args.runner, "--version"], capture_output=True, text=True,
            timeout=RUNNER_VERSION_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        parser.error(f"could not run {args.runner}: {error}")
    if version.returncode != 0:
        parser.error(f"could not read {args.runner} version: "
                     f"{(version.stderr or version.stdout).strip()[:160]}")
    runner_version = (version.stdout or version.stderr).strip()
    if args.runner == "codex" and runner_version != SUPPORTED_CODEX_VERSION:
        parser.error(
            f"unsupported Codex version {runner_version!r}; expected {SUPPORTED_CODEX_VERSION!r}")

    try:
        protocol_content = tuple(
            (name, source.read_bytes()) for name, source in protocol_sources())
        protocol_by_name = dict(protocol_content)
        cases = json.loads(protocol_by_name["tools/eval/register_cases.json"])["cases"]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.error(f"could not read the evaluation protocol: {error}")
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            parser.error(f"unknown case: {args.case}")

    protocol_snapshot = tempfile.TemporaryDirectory(prefix="register-inputs-")
    try:
        protocol_root = pathlib.Path(protocol_snapshot.name)
        frozen_rules = protocol_root / "slop_rules.json"
        frozen_rules.write_bytes(protocol_by_name["tools/eval/slop_rules.json"])
        scoring_rules, scoring_measures = slop_score.load_rules(frozen_rules)
        frozen_fixture = protocol_root / "fixture"
        fixture_prefix = "tools/eval/fixture/"
        for name, content in protocol_content:
            if not name.startswith(fixture_prefix):
                continue
            destination = frozen_fixture / name.removeprefix(fixture_prefix)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        protocol_snapshot.cleanup()
        parser.error(f"could not freeze the evaluation protocol: {error}")

    run_id = (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
              + "-" + uuid.uuid4().hex[:8])
    output_dir = args.output_dir or REPO / ".eval-results" / "register" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    protocol_sha256 = protocol_digest(protocol_content)

    arms = [("baseline", baseline_root)]
    if variant_root:
        arms.append(("variant", variant_root))

    exit_code = 0
    for case in cases:
        print(f"\n{'=' * 72}\n{case['id']}  ({case['skill']} -> {case['artifact']})")
        print(f"{'=' * 72}")
        snapshot = None
        setup_error = None
        try:
            snapshot, frozen_arms, skill_digests = snapshot_arm_roots(arms, case["skill"])
        except (OSError, ValueError) as error:
            frozen_arms = arms
            skill_digests = {}
            setup_error = f"could not snapshot experiment arms: {error}"
        if (setup_error is None and variant_root
                and skill_digests["baseline"] == skill_digests["variant"]):
            setup_error = "baseline and variant skill digests are identical"
        if setup_error:
            exit_code = 1
            print(f"  ERROR {setup_error}")
        codex_context_sha256 = None
        stats_by_arm = {}
        runs_by_arm = {arm_name: [] for arm_name, _ in frozen_arms}
        ambient_hits_by_arm = {arm_name: 0 for arm_name, _ in frozen_arms}
        failures_by_arm = {arm_name: [] for arm_name, _ in frozen_arms}
        execution_sequence = []
        schedule = [] if setup_error else build_arm_schedule(
            frozen_arms, args.repeat, args.seed)
        for position, (arm_name, root, index) in enumerate(schedule, start=1):
            print(f"  {arm_name} {index + 1}/{args.repeat} ... ", end="", flush=True)
            scored, text, ambient, context_digest, error = run_once(
                case, root, args.budget, args.timeout, runner=args.runner,
                model=args.model, scoring_rules=scoring_rules,
                scoring_measures=scoring_measures, fixture=frozen_fixture)
            if context_digest is not None:
                if codex_context_sha256 is None:
                    codex_context_sha256 = context_digest
                elif context_digest != codex_context_sha256:
                    context_error = "Codex effective context changed during the experiment"
                    error = f"{error}; {context_error}" if error else context_error
            stem = f"{case['id']}.{arm_name}.{index + 1}"
            if text:
                (output_dir / f"{stem}.md").write_text(text)
            execution_sequence.append({
                "position": position,
                "pair": index + 1,
                "arm": arm_name,
                "status": "failed" if error else "scored",
            })
            if error:
                failures_by_arm[arm_name].append(error)
                exit_code = 1
                print(f"ERROR {error[:60]}")
                continue
            (output_dir / f"{stem}.score.json").write_text(
                json.dumps(scored, indent=2) + "\n")
            runs_by_arm[arm_name].append(scored)
            if "unslop" in ambient:
                ambient_hits_by_arm[arm_name] += 1
            print(f"{scored['words']:>4}w  "
                  f"{scored['tells_per_100w']:>5} tells/100w")

        prompt = case["prompt"].replace(
            "$SKILL_UNDER_TEST", f"${case['skill']}-under-test")
        audit_by_arm = {
            "experiment": {
                "runner": args.runner,
                "runner_version": runner_version,
                "model": args.model or "runner default",
                "seed": args.seed,
                "case": case["id"],
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "protocol_sha256": protocol_sha256,
                "codex_context_sha256": codex_context_sha256,
                "codex_reasoning_effort": (
                    CODEX_REASONING_EFFORT if args.runner == "codex" else None),
                "codex_user_config": (
                    "ignored in isolated CODEX_HOME" if args.runner == "codex" else None),
                "supported_runner_version": (
                    SUPPORTED_CODEX_VERSION if args.runner == "codex" else None),
                "codex_skill_catalog_contract": (
                    "installed skill absent; staged skill present exactly once before every run"
                    if args.runner == "codex" else None),
                "setup_error": setup_error,
                "arm_sequence": execution_sequence,
            }
        }
        for arm_name, _ in frozen_arms:
            runs = runs_by_arm[arm_name]
            failures = failures_by_arm[arm_name]
            unattempted = args.repeat - len(runs) - len(failures)
            ambient_hits = ambient_hits_by_arm[arm_name]
            stats_by_arm[arm_name] = summarise(runs)
            audit_by_arm[arm_name] = {
                "runner": args.runner,
                "model": args.model or "runner default",
                "skill_sha256": skill_digests.get(arm_name),
                "requested": args.repeat,
                "scored": len(runs),
                "failed": len(failures),
                "unattempted": unattempted,
                "failures": failures,
                "unslop_fired": ambient_hits if args.runner == "claude" else None,
                "ambient_skill_evidence": (
                    "available" if args.runner == "claude" else "unavailable in Codex JSONL"
                ),
                "stats": stats_by_arm[arm_name],
            }
            print_arm(arm_name, stats_by_arm[arm_name], runs)
            print(f"  {len(runs)}/{args.repeat} runs scored"
                  + (f", {len(failures)} failed" if failures else "")
                  + (f", {unattempted} unattempted" if unattempted else ""))
            if runs and args.runner == "claude":
                print(f"  unslop fired in {ambient_hits}/{len(runs)} scored runs")
            elif runs:
                print("  Codex JSONL does not expose ambient skill invocation events")
            for failure in failures:
                print(f"    failed: {failure}")
            if arm_name == "baseline" and len(runs) > 1:
                print_sensitivity(stats_by_arm[arm_name], len(runs))

        if setup_error:
            audit_by_arm["decision"] = {
                "reading": f"invalid experiment; {setup_error}",
            }
        elif variant_root:
            is_complete = all(
                len(runs_by_arm[name]) == args.repeat for name, _ in frozen_arms)
            if is_complete:
                audit_by_arm["decision"] = print_delta(
                    stats_by_arm["baseline"], stats_by_arm["variant"],
                    len(runs_by_arm["baseline"]), len(runs_by_arm["variant"]))
            else:
                print("\nNo delta: at least one arm is incomplete. Rerun the full fixed sample.")
                audit_by_arm["decision"] = {
                    "reading": "incomplete sample; no verdict",
                    "baseline_scored": len(runs_by_arm["baseline"]),
                    "variant_scored": len(runs_by_arm["variant"]),
                }

        (output_dir / f"{case['id']}.summary.json").write_text(
            json.dumps(audit_by_arm, indent=2) + "\n")
        if snapshot is not None:
            snapshot.cleanup()

    print(f"\nRaw results: {output_dir}")
    protocol_snapshot.cleanup()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
