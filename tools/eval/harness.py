#!/usr/bin/env python3
"""Shared plumbing for the eval harnesses in this directory.

The read loops deliberately differ and stay in their own files. run_triggers.py reads the
event stream incrementally through a selector and kills the session on the first routing
decision, because letting the skill run costs roughly 3x per case. run_verify_claims.py
buffers the whole transcript, because its assertions need the tool calls that follow.

Everything around those loops was copied between the two files and drifted. It lives here.
"""
import json
import os
import pathlib
import shutil
import signal
import subprocess
import tempfile

GIT_QUIET = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}


def make_sandbox(prefix, fixture_src, fixture_dest=".", skills=(), post_commit_edit=None):
    """Copy a fixture into a throwaway git repo. Returns (temp_root, repo_path).

    The committed fixtures live inside this repo, so an agent with write access and a
    `commit this` utterance would commit to the skills repo itself. Every run gets its own
    tree, git-initialised so git-shaped utterances have something real to act on.

    Callers are responsible for shutil.rmtree(temp_root).
    """
    temp_root = pathlib.Path(tempfile.mkdtemp(prefix=prefix))
    repo = temp_root / "repo"
    destination = repo / fixture_dest
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fixture_src, destination, dirs_exist_ok=True)

    for skill in skills:
        target = repo / ".claude" / "skills" / pathlib.Path(skill).name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill, target, dirs_exist_ok=True)

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, **GIT_QUIET)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, **GIT_QUIET)
    subprocess.run(["git", "-c", "user.email=eval@local", "-c", "user.name=eval",
                    "commit", "-qm", "fixture"], cwd=repo, check=True, **GIT_QUIET)
    if post_commit_edit:
        post_commit_edit(repo)
    return temp_root, repo


def format_result_error(event, detail_source=None):
    """Render a `result` event's failure as one line, or None when it succeeded."""
    if not event.get("is_error"):
        return None
    status = event.get("api_error_status")
    terminal_reason = event.get("terminal_reason")
    raw = event.get("result", "") if detail_source is None else detail_source
    detail = str(raw).strip().replace("\n", " ")[:160]
    return ": ".join(
        part for part in [
            f"api error {status}" if status else None,
            terminal_reason if terminal_reason and terminal_reason != "completed" else None,
            detail or None,
        ] if part
    ) or "result-error"


def parse_skill_names(event):
    """Every skill named by one assistant event, in order.

    A single assistant message can carry several tool_use blocks, so an ambient skill and
    the real routing choice can arrive together. Callers that want one answer pick from
    this list rather than stopping at the first block.
    """
    if event.get("type") != "assistant":
        return []
    return [(content.get("input") or {}).get("skill")
            for content in event.get("message", {}).get("content", [])
            if content.get("type") == "tool_use" and content.get("name") == "Skill"]


def kill_process_group(proc, partial_stdout=""):
    """SIGKILL the whole group and drain the pipes. Returns (stdout, stderr).

    start_new_session=True on the Popen is what makes the group killable. Without it a
    subagent outlives the kill and keeps billing.

    partial_stdout is whatever the caller already read. A timed-out session still holds a
    transcript worth asserting against, so every path here falls back to it rather than
    reporting an empty run, which would read as a clean miss instead of a truncation.
    """
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        stdout, stderr = proc.communicate(timeout=1)
        return stdout or partial_stdout, stderr
    except subprocess.TimeoutExpired as drain_error:
        drained = drain_error.stdout
        if isinstance(drained, bytes):
            drained = drained.decode(errors="replace")
        for pipe in (proc.stdout, proc.stderr):
            if pipe and not pipe.closed:
                pipe.close()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        return drained or partial_stdout, ""


def verdict(hits, total, has_error=False):
    """PASS only when every run hit. A single run reporting a coin flip as a fact is the
    failure mode --repeat exists to expose, so FLAKY is kept distinct from FAIL."""
    if has_error:
        return "ERROR"
    if hits == total:
        return "PASS"
    return "FLAKY" if hits else "FAIL"


def iter_events(text):
    """Yield parsed JSON objects from a stream-json transcript, skipping unparsable lines."""
    for line in text.splitlines():
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue
