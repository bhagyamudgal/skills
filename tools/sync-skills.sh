#!/usr/bin/env bash
set -euo pipefail

SKILLS_SYNC_REPO="${SKILLS_SYNC_REPO:-bhagyamudgal/skills}"
SKILLS_SYNC_STATE_DIR="${SKILLS_SYNC_STATE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/skills-sync}"
SKILLS_SYNC_LOG="${SKILLS_SYNC_LOG:-$SKILLS_SYNC_STATE_DIR/sync.log}"
SKILLS_SYNC_MARKER="${SKILLS_SYNC_MARKER:-$SKILLS_SYNC_STATE_DIR/last-success}"
SKILLS_SYNC_MAX_AGE_SEC="${SKILLS_SYNC_MAX_AGE_SEC:-86400}"

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
