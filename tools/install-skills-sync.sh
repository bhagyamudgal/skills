#!/usr/bin/env bash
set -euo pipefail

SKILLS_SYNC_RAW_BASE="${SKILLS_SYNC_RAW_BASE:-https://raw.githubusercontent.com/bhagyamudgal/skills/main/tools}"
SKILLS_SYNC_BIN="${SKILLS_SYNC_BIN:-$HOME/.local/bin/skills-sync.sh}"
SKILLS_SYNC_HOOK_COMMAND='$HOME/.local/bin/skills-sync.sh'
CLAUDE_SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
PLIST_LABEL="com.bhagyamudgal.skills-sync"
SKILLS_SYNC_CRON_TAG="bhagyamudgal-skills-sync"
SKILLS_SYNC_LOG_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/skills-sync"

MODE="install"
for arg in "$@"; do
  case "$arg" in
    --uninstall) MODE="uninstall" ;;
    --help|-h)
      printf 'usage: %s [--uninstall]\n' "$(basename "$0")"
      printf 'Installs the daily skills auto-sync script, Claude SessionStart hook, and OS scheduler.\n'
      exit 0
      ;;
    *)
      printf 'unknown argument: %s\n' "$arg" >&2
      exit 2
      ;;
  esac
done

merge_hook() {
  HOOK_COMMAND="$SKILLS_SYNC_HOOK_COMMAND" SETTINGS_PATH="$CLAUDE_SETTINGS" python3 - "$1" <<'PY'
import json, os, sys
action = sys.argv[1]
path = os.environ["SETTINGS_PATH"]
command = os.environ["HOOK_COMMAND"]
try:
    with open(path) as handle:
        settings = json.load(handle)
except FileNotFoundError:
    settings = {}
except json.JSONDecodeError as decode_error:
    print(f"refusing to touch malformed settings file {path}: {decode_error}", file=sys.stderr)
    sys.exit(3)
starts = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
entry = {"matcher": "", "hooks": [{"type": "command", "command": command}]}
present = any(item.get("hooks") == entry["hooks"] for item in starts if isinstance(item, dict))
if action == "add" and not present:
    starts.append(entry)
if action == "remove":
    starts[:] = [item for item in starts if not (isinstance(item, dict) and item.get("hooks") == entry["hooks"])]
    if not starts:
        del settings["hooks"]["SessionStart"]
        if not settings["hooks"]:
            del settings["hooks"]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as handle:
    json.dump(settings, handle, indent=2)
    handle.write("\n")
PY
}

remove_cron() {
  if ! command -v crontab >/dev/null 2>&1; then
    return 0
  fi
  current=$(crontab -l 2>/dev/null || true)
  filtered=$(printf '%s\n' "$current" | grep -v "$SKILLS_SYNC_CRON_TAG" || true)
  if [ -z "$filtered" ]; then
    crontab -r 2>/dev/null || true
  else
    printf '%s\n' "$filtered" | crontab -
  fi
}

if [ "$MODE" = "uninstall" ]; then
  if [ "$(uname)" = "Darwin" ]; then
    launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
  else
    remove_cron
  fi
  merge_hook remove
  rm -f "$SKILLS_SYNC_BIN"
  printf 'skills auto-sync removed. Log and marker left under %s.\n' "$SKILLS_SYNC_LOG_DIR"
  exit 0
fi

mkdir -p "$(dirname "$SKILLS_SYNC_BIN")"
curl -fsSL "$SKILLS_SYNC_RAW_BASE/sync-skills.sh" -o "$SKILLS_SYNC_BIN"
chmod +x "$SKILLS_SYNC_BIN"

merge_hook add

if [ "$(uname)" = "Darwin" ]; then
  plist_target="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
  mkdir -p "$(dirname "$plist_target")"
  curl -fsSL "$SKILLS_SYNC_RAW_BASE/$PLIST_LABEL.plist" | sed "s#__HOME__#$HOME#g" > "$plist_target"
  launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$plist_target"
  printf 'scheduler: launchd daily at 09:00\n'
else
  if command -v crontab >/dev/null 2>&1; then
    current=$(crontab -l 2>/dev/null || true)
    if ! printf '%s\n' "$current" | grep -q "$SKILLS_SYNC_CRON_TAG"; then
      (printf '%s\n' "$current"; printf '0 9 * * * %s # %s\n' "$SKILLS_SYNC_BIN" "$SKILLS_SYNC_CRON_TAG") | crontab -
    fi
    printf 'scheduler: cron daily at 09:00\n'
  else
    printf 'scheduler: crontab not found, SessionStart hook only\n'
  fi
fi

"$SKILLS_SYNC_BIN" --force
printf 'skills auto-sync installed. First sync done, log at %s/sync.log\n' "$SKILLS_SYNC_LOG_DIR"
