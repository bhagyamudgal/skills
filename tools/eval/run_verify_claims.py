#!/usr/bin/env python3
import argparse
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import uuid

import harness

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
CASES = HERE / "verify_claims_cases.json"
FIXTURE = HERE / "verify-claims-fixture"
SKILL = REPO / "skills" / "verify-claims"
CARD_FIELDS = [
    "Claim",
    "Consequence",
    "Counter-hypothesis",
    "Distinguishing observation",
    "Basis evidence",
    "Boundary evidence",
    "State",
    "Limitations",
    "Next action",
    "Independent recheck",
]
CARD_STATES = {"hypothesis", "basis-verified", "verified", "contradicted", "blocked"}
CARD_ANCHOR = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*Claim\b|(?:-[ \t]*)?\*\*Claim:\*\*)",
    re.IGNORECASE | re.MULTILINE,
)


def make_sandbox():
    # The cases address the fixture by its in-repo path, so it has to land at the same
    # path inside the sandbox or every Read in every prompt misses.
    return harness.make_sandbox(
        "verify-claims-eval-", FIXTURE,
        fixture_dest=f"tools/eval/{FIXTURE.name}", skills=[SKILL])


def parse_stream(output):
    """Kept as a name because the cases and this module's tests refer to it."""
    return harness.parse_transcript(output)


def matches_observation(tool_call, observation):
    if not re.search(observation["tool_pattern"], tool_call["name"]):
        return False
    for field, pattern in observation.get("input_field_patterns", {}).items():
        value = tool_call["input"].get(field)
        if not isinstance(value, str) or not re.search(pattern, value, re.IGNORECASE):
            return False
    serialized_input = json.dumps(tool_call["input"], sort_keys=True)
    return (
        all(re.search(pattern, serialized_input, re.IGNORECASE | re.DOTALL)
            for pattern in observation.get("input_patterns", []))
        and all(re.search(pattern, tool_call["result"], re.IGNORECASE | re.DOTALL)
                for pattern in observation.get("result_patterns", []))
    )


def split_claim_blocks(text):
    starts = [match.start() for match in CARD_ANCHOR.finditer(text)]
    if not starts:
        return [text]
    bounds = starts + [len(text)]
    return [text[bounds[index]:bounds[index + 1]] for index in range(len(starts))]


def parse_claim_card(final_text):
    field_names = "|".join(re.escape(field) for field in CARD_FIELDS)
    pattern = re.compile(
        rf"^\s*(?:-\s*)?\*\*({field_names}):\*\*\s*(.*?)"
        rf"(?=^\s*(?:-\s*)?\*\*(?:{field_names}):\*\*|\Z)",
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    return {match.group(1).lower(): match.group(2).strip() for match in pattern.finditer(final_text)}


def normalize_state(value):
    first_line = value.splitlines()[0] if value else ""
    return first_line.replace("`", "").replace("*", "").strip().lower()


def evaluate_case(case, final_text, tool_calls, process_error):
    failures = []
    if process_error:
        failures.append(process_error)
    blocks = split_claim_blocks(final_text)
    cards = [parse_claim_card(block) for block in blocks]
    states = {normalize_state(card.get("state", "")) for card in cards} & CARD_STATES
    if len(states) > 1:
        failures.append(f"conflicting claim cards: {', '.join(sorted(states))}")
    claim_card = cards[-1]
    for field in CARD_FIELDS:
        if not claim_card.get(field.lower()):
            failures.append(f"missing or empty claim-card field: {field}")
    observed_state = normalize_state(claim_card.get("state", ""))
    if observed_state != case["expected_state"]:
        failures.append(
            f"state mismatch: expected {case['expected_state']}, got {observed_state or 'empty'}")
    next_action = claim_card.get("next action", "")
    for pattern in case["required_next_action_patterns"]:
        if not re.search(pattern, next_action, re.IGNORECASE | re.DOTALL):
            failures.append(f"missing next-action pattern: {pattern}")
    for pattern in case.get("forbidden_next_action_patterns", []):
        if re.search(pattern, next_action, re.IGNORECASE | re.DOTALL):
            failures.append(f"forbidden next-action pattern: {pattern}")
    for pattern in case["required_card_patterns"]:
        if not re.search(pattern, blocks[-1], re.IGNORECASE | re.DOTALL):
            failures.append(f"missing claim-card pattern: {pattern}")
    # Whole-message scope is deliberate. A case can assert a value the card is not expected to
    # restate, such as a superseded figure the run had to reconcile rather than silently replace.
    for pattern in case["required_patterns"]:
        if not re.search(pattern, final_text, re.IGNORECASE | re.DOTALL):
            failures.append(f"missing output pattern: {pattern}")
    for pattern in case["required_tool_patterns"]:
        if not any(re.search(pattern, tool_call["name"]) for tool_call in tool_calls):
            failures.append(f"missing tool pattern: {pattern}")
    for observation in case["required_observations"]:
        if not any(matches_observation(tool_call, observation) for tool_call in tool_calls):
            failures.append(f"missing observed tool evidence: {observation['id']}")
    for constraint in case.get("forbidden_tool_inputs", []):
        for tool_call in tool_calls:
            if not re.search(constraint["tool_pattern"], tool_call["name"]):
                continue
            serialized_input = json.dumps(tool_call["input"], sort_keys=True)
            for pattern in constraint["patterns"]:
                if re.search(pattern, serialized_input, re.IGNORECASE | re.DOTALL):
                    failures.append(
                        f"forbidden input pattern for {tool_call['name']}: {pattern}")
    return failures


def run_case(case, budget, timeout):
    temporary_directory, repository = make_sandbox()
    tools = ["Skill", "Read"]
    if case["id"] == "configuration-contradicted":
        tools.append("Glob")
    if case["id"] in {"code-verified", "data-material-reversal"}:
        tools.append("Bash")
    if case["id"] == "data-material-reversal":
        tools.extend(["Agent", "Task"])
    # `--tools` restricts the built-in set, so Edit and Write never exist; `--allowedTools` is a
    # permission allowlist, and under `dontAsk` an unlisted request is denied rather than asked.
    command = [
        "claude", "-p", case["prompt"],
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "dontAsk",
        "--tools", ",".join(tools),
        "--allowedTools", ",".join(tools),
        "--max-budget-usd", str(budget),
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            partial = error.stdout
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            stdout, _ = harness.kill_process_group(process, partial or "")
            final_text, tool_calls, _ = parse_stream(stdout)
            return final_text, tool_calls, "timeout", stdout

        final_text, tool_calls, result_error = parse_stream(stdout)
        process_error = result_error
        if process.returncode != 0 and not process_error:
            process_error = f"claude exited {process.returncode}: {stderr.strip()}"
        return final_text, tool_calls, process_error, stdout
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", help="run one case by id")
    parser.add_argument("--budget", type=float, default=1.50, help="per-case USD cap")
    parser.add_argument("--timeout", type=int, default=300, help="per-case seconds")
    parser.add_argument("--repeat", type=int, default=1,
                        help="runs per case. A twenty-assertion behavioral case is "
                             "non-deterministic — a single run reports a coin flip as a "
                             "fact. Use 3+ for anything you act on.")
    parser.add_argument("--output-dir", type=pathlib.Path)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")

    cases = json.loads(CASES.read_text())["cases"]
    if not cases:
        parser.error(f"no cases defined in {CASES}")
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            parser.error(f"unknown case: {args.case}")

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    output_directory = args.output_dir or REPO / ".eval-results" / "verify-claims" / run_id
    try:
        output_directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        if args.output_dir is not None:
            parser.error(f"output directory already exists: {output_directory}")
        raise

    summaries = []
    for case in cases:
        print(f"[{case['id']}] ", end="", flush=True)
        runs = []
        for run_index in range(args.repeat):
            final_text, tool_calls, process_error, raw_output = run_case(
                case, args.budget, args.timeout)
            failures = evaluate_case(case, final_text, tool_calls, process_error)
            suffix = "" if args.repeat == 1 else f".run{run_index + 1}"
            (output_directory / f"{case['id']}{suffix}.stream.jsonl").write_text(raw_output)
            (output_directory / f"{case['id']}{suffix}.md").write_text(final_text)
            runs.append({
                "tools": [tool_call["name"] for tool_call in tool_calls],
                "failures": failures,
            })
        hits = sum(not run["failures"] for run in runs)
        verdict = harness.verdict(hits, len(runs))
        print(f"{verdict:<5} {hits}/{len(runs)}")
        summaries.append({
            "id": case["id"],
            "lane": case["lane"],
            "verdict": verdict,
            "hits": hits,
            "n": len(runs),
            "runs": runs,
        })

    (output_directory / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    misses = [summary for summary in summaries if summary["verdict"] != "PASS"]
    print(f"{len(summaries) - len(misses)}/{len(summaries)} unanimous")
    print(f"Raw results: {output_directory}")
    for summary in misses:
        occurrences = {}
        for run in summary["runs"]:
            for failure in run["failures"]:
                occurrences[failure] = occurrences.get(failure, 0) + 1
        for failure, count in sorted(occurrences.items(), key=lambda item: -item[1]):
            print(f"  {summary['id']} [{count}/{summary['n']}]: {failure}")
    return 1 if misses else 0


if __name__ == "__main__":
    raise SystemExit(main())
