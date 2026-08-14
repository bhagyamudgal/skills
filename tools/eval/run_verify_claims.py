#!/usr/bin/env python3
import argparse
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import uuid

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


def make_sandbox():
    temporary_directory = pathlib.Path(tempfile.mkdtemp(prefix="verify-claims-eval-"))
    repository = temporary_directory / "repo"
    shutil.copytree(FIXTURE, repository / "tools" / "eval" / FIXTURE.name)
    shutil.copytree(SKILL, repository / ".claude" / "skills" / SKILL.name)
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repository, check=True)
    subprocess.run(
        ["git", "-c", "user.email=eval@local", "-c", "user.name=eval",
         "commit", "-qm", "fixture"],
        cwd=repository,
        check=True,
    )
    return temporary_directory, repository


def parse_stream(output):
    final_text = ""
    assistant_text = []
    tool_calls = []
    tool_calls_by_id = {}
    result_error = None
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant":
            for content in event.get("message", {}).get("content", []):
                if content.get("type") == "text":
                    assistant_text.append(content.get("text", ""))
                elif content.get("type") == "tool_use":
                    tool_call = {
                        "id": content.get("id", ""),
                        "name": content.get("name", ""),
                        "input": content.get("input") or {},
                        "result": "",
                    }
                    tool_calls.append(tool_call)
                    tool_calls_by_id[tool_call["id"]] = tool_call
        elif event.get("type") == "user":
            for content in event.get("message", {}).get("content", []):
                if content.get("type") != "tool_result":
                    continue
                tool_call = tool_calls_by_id.get(content.get("tool_use_id", ""))
                if tool_call:
                    result = content.get("content", "")
                    tool_call["result"] = result if isinstance(result, str) else json.dumps(result)
        elif event.get("type") == "result":
            result = event.get("result", "")
            final_text = result if isinstance(result, str) else json.dumps(result)
            if event.get("is_error"):
                status = event.get("api_error_status")
                terminal_reason = event.get("terminal_reason")
                detail = final_text.strip().replace("\n", " ")[:160]
                result_error = ": ".join(
                    part for part in [
                        f"api error {status}" if status else None,
                        terminal_reason if terminal_reason and terminal_reason != "completed" else None,
                        detail or None,
                    ] if part
                ) or "result-error"
    return "\n".join(assistant_text) or final_text, tool_calls, result_error


def matches_observation(tool_call, observation):
    if not re.search(observation["tool_pattern"], tool_call["name"]):
        return False
    serialized_input = json.dumps(tool_call["input"], sort_keys=True)
    return (
        all(re.search(pattern, serialized_input, re.IGNORECASE | re.DOTALL)
            for pattern in observation.get("input_patterns", []))
        and all(re.search(pattern, tool_call["result"], re.IGNORECASE | re.DOTALL)
                for pattern in observation.get("result_patterns", []))
    )


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
    claim_card = parse_claim_card(final_text)
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
    command = [
        "claude", "-p", case["prompt"],
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "dontAsk",
        "--max-budget-usd", str(budget),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        final_text, tool_calls, result_error = parse_stream(completed.stdout)
        process_error = result_error
        if completed.returncode != 0 and not process_error:
            process_error = f"claude exited {completed.returncode}: {completed.stderr.strip()}"
        return final_text, tool_calls, process_error, completed.stdout
    except subprocess.TimeoutExpired as error:
        output = error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout or ""
        final_text, tool_calls, _ = parse_stream(output)
        return final_text, tool_calls, "timeout", output
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", help="run one case by id")
    parser.add_argument("--budget", type=float, default=1.50, help="per-case USD cap")
    parser.add_argument("--timeout", type=int, default=300, help="per-case seconds")
    parser.add_argument("--output-dir", type=pathlib.Path)
    args = parser.parse_args()

    cases = json.loads(CASES.read_text())["cases"]
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            parser.error(f"unknown case: {args.case}")

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    output_directory = args.output_dir or REPO / ".eval-results" / "verify-claims" / run_id
    output_directory.mkdir(parents=True, exist_ok=False)

    summaries = []
    for case in cases:
        print(f"[{case['id']}] ", end="", flush=True)
        final_text, tool_calls, process_error, raw_output = run_case(
            case, args.budget, args.timeout)
        failures = evaluate_case(case, final_text, tool_calls, process_error)
        verdict = "PASS" if not failures else "FAIL"
        print(verdict)
        (output_directory / f"{case['id']}.stream.jsonl").write_text(raw_output)
        (output_directory / f"{case['id']}.md").write_text(final_text)
        summaries.append({
            "id": case["id"],
            "lane": case["lane"],
            "verdict": verdict,
            "tools": [tool_call["name"] for tool_call in tool_calls],
            "failures": failures,
        })

    (output_directory / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    failed = [summary for summary in summaries if summary["verdict"] == "FAIL"]
    print(f"{len(summaries) - len(failed)}/{len(summaries)} passed")
    print(f"Raw results: {output_directory}")
    for summary in failed:
        for failure in summary["failures"]:
            print(f"  {summary['id']}: {failure}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
