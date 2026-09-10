#!/usr/bin/env bash
set -euo pipefail

SKILLS_SYNC_REPO="${SKILLS_SYNC_REPO:-bhagyamudgal/skills}"
SKILLS_SYNC_STATE_DIR="${SKILLS_SYNC_STATE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/skills-sync}"
SKILLS_SYNC_LOG="${SKILLS_SYNC_LOG:-$SKILLS_SYNC_STATE_DIR/sync.log}"
SKILLS_SYNC_MARKER="${SKILLS_SYNC_MARKER:-$SKILLS_SYNC_STATE_DIR/last-success}"
SKILLS_SYNC_MAX_AGE_SEC="${SKILLS_SYNC_MAX_AGE_SEC:-86400}"
SKILLS_SYNC_LOCK_DIR="${SKILLS_SYNC_LOCK_DIR:-$SKILLS_SYNC_STATE_DIR/sync.lock}"

prefer_tool_dirs() {
  for bin_dir in /usr/local/bin /opt/homebrew/bin "$HOME/.local/bin" "$HOME/.nvm/versions/node/"*/bin; do
    [ -d "$bin_dir" ] || continue
    case ":$PATH:" in
      *":$bin_dir:"*) ;;
      *) PATH="$bin_dir:$PATH" ;;
    esac
  done
  export PATH
}

acquire_lock() {
  if mkdir "$SKILLS_SYNC_LOCK_DIR" 2>/dev/null; then
    printf '%s' "$$" > "$SKILLS_SYNC_LOCK_DIR/pid"
    return 0
  fi
  lock_pid=$(cat "$SKILLS_SYNC_LOCK_DIR/pid" 2>/dev/null || true)
  case "$lock_pid" in
    ''|*[!0-9]*) return 1 ;;
  esac
  if kill -0 "$lock_pid" 2>/dev/null; then
    return 1
  fi
  rm -rf "$SKILLS_SYNC_LOCK_DIR"
  if mkdir "$SKILLS_SYNC_LOCK_DIR" 2>/dev/null; then
    printf '%s' "$$" > "$SKILLS_SYNC_LOCK_DIR/pid"
    return 0
  fi
  return 1
}

release_lock() {
  lock_pid=$(cat "$SKILLS_SYNC_LOCK_DIR/pid" 2>/dev/null || true)
  if [ "$lock_pid" = "$$" ]; then
    rm -rf "$SKILLS_SYNC_LOCK_DIR"
  fi
}

FORCE=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --help|-h)
      printf 'usage: %s [--force]\n' "$(basename "$0")"
      printf 'Syncs all skills from %s to the global scope of every detected agent.\n' "$SKILLS_SYNC_REPO"
      printf 'Skips the network when the last success is under SKILLS_SYNC_MAX_AGE_SEC old.\n'
      exit 0
      ;;
    *)
      printf 'unknown argument: %s\n' "$arg" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$SKILLS_SYNC_STATE_DIR"
prefer_tool_dirs

if ! command -v npx >/dev/null 2>&1; then
  printf '[%s] npx not found on PATH, sync skipped\n' "$(date -u +%FT%TZ)" >>"$SKILLS_SYNC_LOG" 2>&1
  printf 'npx not found on PATH. Install Node or expose its bin directory via PATH.\n' >&2
  exit 3
fi

if ! acquire_lock; then
  printf '[%s] another sync holds the lock, skipping\n' "$(date -u +%FT%TZ)" >>"$SKILLS_SYNC_LOG" 2>&1
  exit 0
fi
trap release_lock EXIT

marker_fresh() {
  [ -f "$SKILLS_SYNC_MARKER" ] || return 1
  if date -r "$SKILLS_SYNC_MARKER" +%s >/dev/null 2>&1; then
    marker_now=$(date +%s)
    marker_mtime=$(date -r "$SKILLS_SYNC_MARKER" +%s)
  else
    marker_now=$(date +%s)
    marker_mtime=$(stat -c %Y "$SKILLS_SYNC_MARKER")
  fi
  [ $((marker_now - marker_mtime)) -lt "$SKILLS_SYNC_MAX_AGE_SEC" ]
}

if [ "$FORCE" -eq 0 ] && marker_fresh; then
  exit 0
fi

{
  printf '[%s] sync start repo=%s\n' "$(date -u +%FT%TZ)" "$SKILLS_SYNC_REPO"
  npx -y skills@latest add "$SKILLS_SYNC_REPO" --all -g -y
  npx -y skills@latest update -g -y
  printf '[%s] sync ok\n' "$(date -u +%FT%TZ)"
} >>"$SKILLS_SYNC_LOG" 2>&1

touch "$SKILLS_SYNC_MARKER"
