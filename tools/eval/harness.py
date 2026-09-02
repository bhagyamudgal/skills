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

    # A global commit.gpgsign with no key, or a core.hooksPath pointing at a failing hook,
    # fails here. Discarding git's stderr leaves only "returned non-zero exit status 128".
    for argv in (["git", "init", "-q"],
                 ["git", "add", "-A"],
                 ["git", "-c", "user.email=eval@local", "-c", "user.name=eval",
                  "commit", "-qm", "fixture"]):
        done = subprocess.run(argv, cwd=repo, capture_output=True, text=True)
        if done.returncode != 0:
            raise RuntimeError(
                f"sandbox setup failed: {' '.join(argv)} exited {done.returncode}: "
                f"{(done.stderr or done.stdout).strip()[:300]}")
    if post_commit_edit:
        post_commit_edit(repo)
    return temp_root, repo


# A result event can signal failure through `subtype` without setting `is_error`, so keying
# only on the boolean scores a truncated or turn-capped run as clean.
FAILURE_SUBTYPES = frozenset({"error_max_turns", "error_during_execution"})


def format_result_error(event, detail_source=None):
    """Render a `result` event's failure as one line, or None when it succeeded."""
    subtype = event.get("subtype")
    if not event.get("is_error") and subtype not in FAILURE_SUBTYPES:
        return None
    status = event.get("api_error_status")
    terminal_reason = event.get("terminal_reason")
    raw = event.get("result", "") if detail_source is None else detail_source
    detail = str(raw).strip().replace("\n", " ")[:160]
    return ": ".join(
        part for part in [
            f"api error {status}" if status else None,
            subtype if subtype in FAILURE_SUBTYPES else None,
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


def parse_transcript(output):
    """Read a buffered stream-json transcript. Returns (final_text, tool_calls, error).

    Each tool call carries the result that came back for it, matched by tool_use_id, so a
    caller can assert on what a tool actually returned and not just that it was called.
    """
    final_text = ""
    last_assistant_message = ""
    tool_calls = []
    tool_calls_by_id = {}
    result_error = None
    saw_result = False
    for event in iter_events(output):
        if event.get("type") == "assistant":
            message_text = []
            for content in event.get("message", {}).get("content", []):
                if content.get("type") == "text":
                    message_text.append(content.get("text", ""))
                elif content.get("type") == "tool_use":
                    tool_call = {
                        "id": content.get("id", ""),
                        "name": content.get("name", ""),
                        "input": content.get("input") or {},
                        "result": "",
                    }
                    tool_calls.append(tool_call)
                    tool_calls_by_id[tool_call["id"]] = tool_call
            if any(text.strip() for text in message_text):
                last_assistant_message = "\n".join(message_text)
        elif event.get("type") == "user":
            for content in event.get("message", {}).get("content", []):
                if content.get("type") != "tool_result":
                    continue
                tool_call = tool_calls_by_id.get(content.get("tool_use_id", ""))
                if tool_call:
                    result = content.get("content", "")
                    tool_call["result"] = (result if isinstance(result, str)
                                           else json.dumps(result))
        elif event.get("type") == "result":
            saw_result = True
            result = event.get("result", "")
            final_text = result if isinstance(result, str) else json.dumps(result)
            result_error = format_result_error(event, final_text)
    # No result event means the transcript was cut off, so the text below is a retracted
    # draft. Scoring one as finished is how a truncated run reads as a clean one.
    if not saw_result and result_error is None:
        result_error = "missing result event, transcript truncated"
    # The `result` event carries the final assistant message; earlier messages are drafts,
    # and joining them lets a card be assembled field-wise across drafts the model retracted.
    return final_text or last_assistant_message, tool_calls, result_error


def kill_process_group(proc, partial_stdout=""):
    """SIGKILL the whole group and drain the pipes. Returns (stdout, stderr).

    start_new_session=True on the Popen is what makes the group killable. Without it a
    subagent outlives the kill and keeps billing.

    partial_stdout is whatever the caller already read. A timed-out session still holds a
    transcript worth asserting against, so every path here falls back to it rather than
    reporting an empty run, which would read as a clean miss instead of a truncation.
    """
    # Only signal a process that has not been reaped. Once wait() has collected it the pid
    # can be recycled, and killpg would deliver SIGKILL to an unrelated process group.
    if proc.returncode is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        stdout, stderr = proc.communicate(timeout=1)
        return stdout or partial_stdout, stderr
    except subprocess.TimeoutExpired as drain_error:
        def decoded(stream):
            return stream.decode(errors="replace") if isinstance(stream, bytes) else stream

        drained = decoded(drain_error.stdout)
        drained_stderr = decoded(drain_error.stderr) or ""
        for pipe in (proc.stdout, proc.stderr):
            if pipe and not pipe.closed:
                pipe.close()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        return drained or partial_stdout, drained_stderr


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
