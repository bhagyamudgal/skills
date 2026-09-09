#!/usr/bin/env python3
"""Gather standup material: GitHub activity, unpushed local work, agent sessions."""

import argparse
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, time, timedelta


def local_tz():
    return datetime.now().astimezone().tzinfo


STANDUP_HOUR = 10
CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
CODEX_SESSIONS_DIR = os.path.expanduser("~/.codex/sessions")
OPENCODE_DB = os.path.expanduser("~/.local/share/opencode/opencode.db")


def run(cmd, cwd=None, timeout=60):
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return out.returncode, out.stdout, out.stderr
    except Exception as exc:
        return 1, "", str(exc)


def is_weekend(d):
    return d.weekday() >= 5


def previous_workday(d):
    prev = d - timedelta(days=1)
    while is_weekend(prev):
        prev -= timedelta(days=1)
    return prev


def last_friday_before(d):
    cur = d
    while cur.weekday() != 4:
        cur -= timedelta(days=1)
    return cur


def at_standup(d, tz):
    return datetime.combine(d, time(STANDUP_HOUR, 0), tzinfo=tz)


def default_window(now):
    tz = now.tzinfo
    today = now.date()
    if now.hour < STANDUP_HOUR:
        start = at_standup(previous_workday(today), tz)
        label = "since previous standup"
    elif not is_weekend(today):
        start = at_standup(today, tz)
        label = "since today's standup"
    else:
        start = at_standup(last_friday_before(today), tz)
        label = "since last Friday (weekend)"
    return start, now, label


def parse_iso_local(value, tz):
    if len(value) == 10:
        d = datetime.strptime(value, "%Y-%m-%d").date()
        return at_standup(d, tz)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def gh_user():
    code, out, _ = run(["gh", "api", "user", "--jq", ".login"])
    return out.strip() if code == 0 and out.strip() else None


def gh_json(args):
    code, out, err = run(["gh"] + args, timeout=90)
    if code != 0:
        return None, err.strip()
    try:
        return json.loads(out), None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def in_window(iso_str, start, end):
    if not iso_str:
        return False
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(start.tzinfo)
    except ValueError:
        return False
    return start <= dt <= end


def detect_org(repo_root):
    code, out, _ = run(["git", "remote", "get-url", "origin"], cwd=repo_root)
    if code != 0:
        return None
    match = re.search(r"github\.com[:/]([^/]+)/", out.strip())
    return match.group(1) if match else None


def gather_github(user, org, start, end):
    wide_lo = (start - timedelta(days=1)).strftime("%Y-%m-%d")
    wide_hi = (end + timedelta(days=1)).strftime("%Y-%m-%d")
    result = {"commits": [], "prs_created": [], "prs_reviewed": [], "prs_merged": [], "errors": []}
    owner_filter = [f"--owner={org}"] if org else []

    commits, err = gh_json([
        "search", "commits", f"--author={user}", *owner_filter,
        f"author-date:{wide_lo}..{wide_hi}", "--limit", "100",
        "--json", "repository,sha,commit,url",
    ])
    if err:
        result["errors"].append(f"commits: {err}")
    for entry in commits or []:
        adate = entry.get("commit", {}).get("author", {}).get("date", "")
        if not in_window(adate, start, end):
            continue
        msg = entry.get("commit", {}).get("message", "").splitlines()[0]
        result["commits"].append({
            "repo": entry.get("repository", {}).get("name", ""),
            "sha": entry.get("sha", "")[:9],
            "message": msg,
            "is_merge": msg.lower().startswith("merge "),
            "date": adate,
            "url": entry.get("url", ""),
        })

    created, err = gh_json([
        "search", "prs", f"--author={user}", *owner_filter,
        f"created:{wide_lo}..{wide_hi}", "--limit", "50",
        "--json", "number,title,url,state,repository,createdAt",
    ])
    if err:
        result["errors"].append(f"prs_created: {err}")
    for pr in created or []:
        if not in_window(pr.get("createdAt"), start, end):
            continue
        result["prs_created"].append({
            "repo": pr.get("repository", {}).get("name", ""),
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "state": pr.get("state", ""),
            "url": pr.get("url", ""),
        })

    merged, err = gh_json([
        "search", "prs", f"--author={user}", *owner_filter,
        f"merged:{wide_lo}..{wide_hi}", "--limit", "50",
        "--json", "number,title,url,repository,closedAt",
    ])
    if err:
        result["errors"].append(f"prs_merged: {err}")
    for pr in merged or []:
        if not in_window(pr.get("closedAt"), start, end):
            continue
        result["prs_merged"].append({
            "repo": pr.get("repository", {}).get("name", ""),
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "url": pr.get("url", ""),
        })

    reviewed, err = gh_json([
        "search", "prs", f"--reviewed-by={user}", *owner_filter,
        f"updated:{wide_lo}..{wide_hi}", "--limit", "40",
        "--json", "number,title,url,repository,author",
    ])
    if err:
        result["errors"].append(f"prs_reviewed: {err}")
    for pr in reviewed or []:
        author = (pr.get("author") or {}).get("login", "")
        if author == user:
            continue
        result["prs_reviewed"].append({
            "repo": pr.get("repository", {}).get("name", ""),
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "author": author,
            "url": pr.get("url", ""),
        })
    return result


def list_worktrees(repo_root):
    code, out, _ = run(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
    if code != 0:
        return [(repo_root, None)]
    entries = []
    path = None
    branch = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line.startswith("branch "):
            branch = line[len("branch "):].replace("refs/heads/", "")
        elif line == "":
            if path:
                entries.append((path, branch))
            path, branch = None, None
    if path:
        entries.append((path, branch))
    return entries


def gather_local(repo_root):
    result = {"repo_root": repo_root, "worktrees": [], "stashes": [], "errors": []}
    if not os.path.isdir(repo_root):
        result["errors"].append(f"repo root not found: {repo_root}")
        return result

    code, out, _ = run(["git", "stash", "list"], cwd=repo_root)
    if code == 0 and out.strip():
        result["stashes"] = out.strip().splitlines()

    for path, branch in list_worktrees(repo_root):
        entry = {"path": path, "branch": branch, "uncommitted": [], "unpushed": []}
        code, out, _ = run(["git", "status", "--porcelain"], cwd=path)
        if code == 0 and out.strip():
            entry["uncommitted"] = out.strip().splitlines()
        code, out, _ = run(
            ["git", "log", "--oneline", "-30", "HEAD", "--not", "--remotes=origin"],
            cwd=path,
        )
        if code == 0 and out.strip():
            entry["unpushed"] = out.strip().splitlines()
        if entry["uncommitted"] or entry["unpushed"]:
            result["worktrees"].append(entry)
    return result


def extract_claude_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


NOISE_MARKERS = ("<command-message>", "<command-name>", "<local-command",
                 "tool_use_id", "[Request interrupted", "<system-reminder>",
                 "caveat:", "<user-prompt-submit-hook>")


def gather_claude_sessions(repo_basename, start, end, tz):
    found = []
    errors = []
    if not os.path.isdir(CLAUDE_PROJECTS_DIR):
        return found, ["no Claude projects dir"]
    for entry in os.listdir(CLAUDE_PROJECTS_DIR):
        if repo_basename.lower() not in entry.lower():
            continue
        proj_dir = os.path.join(CLAUDE_PROJECTS_DIR, entry)
        if not os.path.isdir(proj_dir):
            continue
        for fname in os.listdir(proj_dir):
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(proj_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=tz)
            except OSError:
                continue
            if mtime < start - timedelta(days=1):
                continue
            prompts = []
            title = None
            branch = None
            try:
                with open(fpath, encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            doc = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if doc.get("type") == "ai-title" and not title:
                            title = doc.get("title") or doc.get("message")
                        if doc.get("type") != "user" or doc.get("isSidechain"):
                            continue
                        if not in_window(doc.get("timestamp", ""), start, end):
                            continue
                        branch = doc.get("gitBranch") or branch
                        text = extract_claude_text((doc.get("message") or {}).get("content"))
                        text = text.strip()
                        if not text or any(m in text for m in NOISE_MARKERS):
                            continue
                        prompts.append(text[:400])
            except OSError:
                continue
            if prompts:
                found.append({
                    "agent": "claude",
                    "title": title,
                    "branch": branch,
                    "session_file": fname,
                    "prompt_count": len(prompts),
                    "prompts": prompts[:12],
                })
    return found, errors


def codex_user_texts(doc):
    texts = []
    payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else None
    if not payload:
        return texts
    item = payload.get("item") if isinstance(payload.get("item"), dict) else None
    if not item or item.get("type") != "UserMessage":
        return texts
    for block in item.get("content") or []:
        if isinstance(block, dict) and block.get("text"):
            texts.append(block.get("text", ""))
    return texts


def gather_codex_sessions(repo_basename, start, end, tz):
    found = []
    errors = []
    if not os.path.isdir(CODEX_SESSIONS_DIR):
        return found, []
    for root, _, files in os.walk(CODEX_SESSIONS_DIR):
        for fname in files:
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(root, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=tz)
            except OSError:
                continue
            if mtime < start - timedelta(days=1):
                continue
            prompts = []
            cwd = None
            try:
                with open(fpath, encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            doc = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if doc.get("type") == "session_meta":
                            payload = doc.get("payload") or {}
                            cwd = payload.get("cwd") or cwd
                        stamp = doc.get("timestamp", "")
                        if not in_window(stamp, start, end):
                            continue
                        for text in codex_user_texts(doc):
                            text = text.strip()
                            if text:
                                prompts.append(text[:400])
            except OSError:
                continue
            if cwd and repo_basename.lower() not in cwd.lower():
                continue
            if prompts:
                found.append({
                    "agent": "codex",
                    "title": None,
                    "branch": None,
                    "session_file": fname,
                    "prompt_count": len(prompts),
                    "prompts": prompts[:12],
                })
    return found, errors


def gather_opencode_sessions(repo_basename, start, end, tz):
    found = []
    errors = []
    if not os.path.isfile(OPENCODE_DB):
        return found, []
    try:
        conn = sqlite3.connect(OPENCODE_DB)
    except sqlite3.Error as exc:
        return found, [f"opencode db: {exc}"]
    try:
        rows = conn.execute(
            "SELECT id, directory, title, time_created, time_updated FROM session"
        ).fetchall()
    except sqlite3.Error as exc:
        conn.close()
        return found, [f"opencode session query: {exc}"]
    lo_ms = int((start - timedelta(days=1)).timestamp() * 1000)
    for session_id, directory, title, created_ms, updated_ms in rows:
        if (updated_ms or 0) < lo_ms:
            continue
        if repo_basename.lower() not in (directory or "").lower():
            continue
        try:
            parts = conn.execute(
                "SELECT m.data, p.data, p.time_created FROM part p "
                "JOIN message m ON m.id = p.message_id "
                "WHERE p.session_id = ?", (session_id,)
            ).fetchall()
        except sqlite3.Error:
            continue
        prompts = []
        for message_data, part_data, part_ms in parts:
            try:
                part_dt = datetime.fromtimestamp((part_ms or 0) / 1000, tz=tz)
            except (OSError, OverflowError, ValueError):
                continue
            if not (start <= part_dt <= end):
                continue
            try:
                message = json.loads(message_data or "{}")
            except json.JSONDecodeError:
                continue
            if message.get("role") != "user":
                continue
            try:
                part = json.loads(part_data or "{}")
            except json.JSONDecodeError:
                continue
            if part.get("type") != "text" or not part.get("text", "").strip():
                continue
            prompts.append(part.get("text", "").strip()[:400])
        if prompts:
            found.append({
                "agent": "opencode",
                "title": title,
                "branch": None,
                "session_file": session_id,
                "prompt_count": len(prompts),
                "prompts": prompts[:12],
            })
    conn.close()
    return found, errors


def gather_sessions(repo_basename, start, end, tz):
    result = {"sessions": [], "errors": []}
    for gatherer in (gather_claude_sessions, gather_codex_sessions, gather_opencode_sessions):
        found, errors = gatherer(repo_basename, start, end, tz)
        result["sessions"].extend(found)
        result["errors"].extend(errors)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=None)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--start", help="ISO or YYYY-MM-DD (local). Overrides default window.")
    parser.add_argument("--end", help="ISO or YYYY-MM-DD (local). Defaults to now.")
    parser.add_argument("--no-github", action="store_true")
    parser.add_argument("--no-local", action="store_true")
    parser.add_argument("--no-sessions", action="store_true")
    args = parser.parse_args()

    tz = local_tz()
    now = datetime.now(tz)
    if args.start:
        start = parse_iso_local(args.start, tz)
        end = parse_iso_local(args.end, tz) if args.end else now
        window_label = "explicit range"
    else:
        start, end, window_label = default_window(now)

    repo_root = os.path.abspath(os.path.expanduser(args.repo_root)) if args.repo_root else os.getcwd()
    repo_basename = os.path.basename(repo_root.rstrip("/"))
    org = args.org or detect_org(repo_root)
    user = gh_user()

    payload = {
        "generated_at": now.isoformat(),
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": window_label,
            "start_readable": start.strftime("%a %d %b %Y %H:%M %Z"),
            "end_readable": end.strftime("%a %d %b %Y %H:%M %Z"),
        },
        "org": org,
        "github_user": user,
        "repo_root": repo_root,
    }

    if args.no_github:
        payload["github"] = {"skipped": True}
    elif not user:
        payload["github"] = {"error": "could not resolve gh user (is gh authenticated?)"}
    else:
        payload["github"] = gather_github(user, org, start, end)

    payload["local"] = {"skipped": True} if args.no_local else gather_local(repo_root)
    payload["sessions"] = (
        {"skipped": True} if args.no_sessions
        else gather_sessions(repo_basename, start, end, tz)
    )

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
