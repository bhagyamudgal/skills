#!/usr/bin/env python3
"""Number, read and write the /review-pr state file for one PR.

round prints CURRENT_ROUND, one past the highest round posted on the PR or recorded in the state file.
read prints the state as JSON, converting a legacy YAML state file on every read until write saves JSON.
write validates a new state and replaces the file atomically, refusing to lower last_round or drop a stored finding.
Exits 2 with one line per problem on stderr, or 3 when a legacy YAML state file does not convert cleanly.
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

STATUSES = ["active", "resolved", "dismissed", "wontfix", "regression"]
IDENTITY_FIELDS = ["file", "enclosing_symbol", "rule_class"]
RUN_MARKER_ROUND = re.compile(r"review-pr:run [^>]*round=([0-9]+)")
REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
PROBLEM_EXIT = 2
LEGACY_EXIT = 3
REPAIR_ADVICE = "if a newer ruby parses it, put that ruby first on PATH; otherwise repair the file in place until review_state.py read converts it"
YAML_TO_JSON = """
require "yaml"
require "json"
typed_keys = %w[pr last_round round round_first_seen round_resolved github_comment_id handled]
null_text = /\\A(~|null|Null|NULL|)\\z/
begin
  stream = Psych.parse_stream(File.read(ARGV[0]))
rescue Psych::SyntaxError => error
  abort "ruby #{RUBY_VERSION} cannot parse it: #{error.message}"
end
abort "it holds #{stream.children.size} YAML documents, expected one" unless stream.children.size == 1
as_text = ->(node) do
  return unless node.is_a?(Psych::Nodes::Scalar) && node.plain && !node.value.match?(null_text)
  node.plain = false
  node.quoted = true
  node.style = Psych::Nodes::Scalar::SINGLE_QUOTED
end
walk = ->(node) do
  case node
  when Psych::Nodes::Mapping
    node.children.each_slice(2) { |key, value| as_text.(value) unless typed_keys.include?(key.value) }
  when Psych::Nodes::Sequence
    node.children.each(&as_text)
  end
  (node.children || []).each(&walk)
end
walk.(stream)
puts JSON.generate(YAML.safe_load(stream.to_yaml))
"""


class StateError(Exception):
    def __init__(self, message, exit_code=PROBLEM_EXIT):
        super().__init__(message)
        self.exit_code = exit_code


def run_marker(head_sha, round_number):
    return f"<!-- review-pr:run sha={head_sha} round={round_number} -->"


def run_command(arguments, missing_error):
    try:
        return subprocess.run(arguments, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise missing_error


def highest_posted_round(repo, pr):
    completed = run_command(["gh", "pr", "view", str(pr), "--repo", repo, "--json", "reviews"],
                            StateError(f"gh is not installed, so the rounds posted on {repo}#{pr} cannot be read"))
    if completed.returncode != 0:
        raise StateError(f"gh pr view {pr} --repo {repo} failed: {completed.stderr.strip()}")
    try:
        bodies = [review.get("body") or "" for review in json.loads(completed.stdout)["reviews"]]
        return max((int(found) for body in bodies for found in RUN_MARKER_ROUND.findall(body)), default=0)
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as error:
        raise StateError(f"gh pr view {pr} --repo {repo} returned unreadable reviews: {error!r}")


def empty_state(repo, pr):
    return {"pr": pr, "repo": repo, "findings": [], "last_round": 0}


def legacy_path(path):
    return path.with_suffix(".yml")


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as error:
        raise StateError(f"cannot read state file {path}: {error}")


def legacy_error(path, reason, advice=REPAIR_ADVICE):
    return StateError(f"legacy YAML state {path} does not convert ({reason}); {advice}; never write JSON over it", LEGACY_EXIT)


def convert_legacy(path):
    completed = run_command(["ruby", "-e", YAML_TO_JSON, str(path)], legacy_error(path, "ruby is not installed", "install ruby, which converts it"))
    if completed.returncode != 0:
        raise legacy_error(path, next(iter(completed.stderr.strip().splitlines()), f"ruby exited {completed.returncode}"))
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise legacy_error(path, f"ruby printed no JSON: {error}")


def is_count(value, minimum):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def stored_problems(state, repo, pr):
    if not isinstance(state, dict):
        return ["it must hold one JSON object"]
    problems = []
    if not is_count(state.get("last_round"), 0):
        problems.append("last_round must be a whole number")
    if not isinstance(state.get("findings"), list):
        problems.append("findings must be a list")
    if "pr" in state and state["pr"] != pr:
        problems.append(f"it belongs to PR {state['pr']!r}, not {pr}")
    if isinstance(state.get("repo"), str) and state["repo"].lower() != repo.lower():
        problems.append(f"it belongs to {state['repo']}, not {repo}")
    return problems


def read_state(path, repo, pr):
    text = read_text(path)
    if text is None:
        legacy = legacy_path(path)
        if read_text(legacy) is None:
            return empty_state(repo, pr)
        state = convert_legacy(legacy)
        problems = stored_problems(state, repo, pr)
        if problems:
            raise legacy_error(legacy, "; ".join(problems))
        return state
    try:
        state = json.loads(text)
    except json.JSONDecodeError as error:
        raise StateError(f"state file {path} is not valid JSON ({error}); stop and report it, never delete or replace it")
    problems = stored_problems(state, repo, pr)
    if problems:
        raise StateError("\n".join(f"state file {path}: {problem}; stop and report it, never delete or replace it" for problem in problems))
    return state


def finding_problems(index, finding):
    label = f"findings[{index}]"
    if not isinstance(finding, dict):
        return [f"{label} must be an object"]
    problems = [f"{label}.{field} is required" for field in IDENTITY_FIELDS if not isinstance(finding.get(field), str) or not finding[field].strip()]
    if not isinstance(finding.get("id"), str) or not re.fullmatch(r"[0-9a-f]{10}", finding["id"]):
        problems.append(f"{label}.id must be the 10-hex finding ID from finding-state-schema.md, not a label like S1")
    if finding.get("status") not in STATUSES:
        problems.append(f"{label}.status must be one of {STATUSES}")
    return problems


def state_problems(state):
    if not isinstance(state, dict):
        return ["the state must be one JSON object"]
    problems = []
    if not is_count(state.get("pr"), 1):
        problems.append("pr must be the PR number")
    if not isinstance(state.get("repo"), str) or not REPO_NAME.fullmatch(state["repo"]):
        problems.append("repo must be <owner>/<name>")
    if not is_count(state.get("last_round"), 1):
        problems.append("last_round must be the round this run posted, at least 1")
    findings = state.get("findings")
    if not isinstance(findings, list):
        return problems + ["findings must be a list"]
    for index, finding in enumerate(findings):
        problems.extend(finding_problems(index, finding))
    ids = [finding.get("id") for finding in findings if isinstance(finding, dict)]
    problems.extend(f"finding id {finding_id} appears more than once" for finding_id in sorted({i for i in ids if isinstance(i, str) and ids.count(i) > 1}))
    return problems


def stored_ids(state):
    return {str(finding["id"]) for finding in state["findings"] if isinstance(finding, dict) and finding.get("id") is not None}


def history_problems(path, state, drops):
    stored = read_state(path, state["repo"], state["pr"])
    problems = []
    if state["last_round"] < stored["last_round"]:
        problems.append(f"last_round {state['last_round']} is below round {stored['last_round']} already stored for this PR; "
                        f"rebuild the state from review_state.py read instead of starting over")
    dropped = sorted(stored_ids(stored) - stored_ids(state) - set(drops))
    if dropped:
        problems.append(f"the new state drops stored findings {', '.join(dropped)}; carry every stored entry forward, "
                        f"or pass --drop <id> for each entry Phase 4 step 6 recomputed or removed")
    return problems


def replace_atomically(path, state):
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except OSError as error:
        if temporary is not None:
            pathlib.Path(temporary).unlink(missing_ok=True)
        raise StateError(f"cannot write {path}: {error}")
    sync_directory(path)


def sync_directory(path):
    try:
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as error:
        print(f"saved {path}, but its directory could not be synced to disk: {error}", file=sys.stderr)


def write_state(path, state, drops=()):
    problems = state_problems(state)
    problems = problems or history_problems(path, state, drops)
    if problems:
        raise StateError("\n".join(problems))
    replace_atomically(path, state)


def current_round(path, repo, pr):
    return max(highest_posted_round(repo, pr), read_state(path, repo, pr)["last_round"]) + 1


def read_input(input_path):
    try:
        return json.loads(pathlib.Path(input_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise StateError(f"cannot read {input_path}: {error}")


def run(args):
    path = pathlib.Path(args.file)
    if args.command == "round":
        print(current_round(path, args.repo, args.pr))
    elif args.command == "read":
        print(json.dumps(read_state(path, args.repo, args.pr), ensure_ascii=False, indent=2))
    else:
        write_state(path, read_input(args.input), args.drop)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["round", "read"]:
        command = commands.add_parser(name)
        command.add_argument("--repo", required=True, help="<owner>/<name>")
        command.add_argument("--pr", type=int, required=True, help="PR number")
        command.add_argument("--file", required=True, help="$STATE_FILE")
    write = commands.add_parser("write")
    write.add_argument("--file", required=True, help="$STATE_FILE")
    write.add_argument("--input", required=True, help="JSON file holding the complete new state")
    write.add_argument("--drop", action="append", default=[], help="a stored finding id this write removes on purpose")
    args = parser.parse_args(argv)
    try:
        run(args)
    except StateError as error:
        print(error, file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
