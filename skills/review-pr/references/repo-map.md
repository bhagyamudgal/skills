# Shared-package repo map: `repo_map_files` / `repo_map_exports`

This file holds the one copy of the repo-map shell. Three skills run it, each in its own Phase 1, each
feeding a different consumer:

- **`/review-pr`**: main, when `packages/` or `apps/` exists. Both outputs go into
  Subagent 1's prompt for Q6.
- **`/fix-pr-review`**: main, when `packages/` or `apps/` exists. Both outputs go into the
  Phase 3 triage subagent's prompt for reusability-aware classification.
- **`/harden-plan`**: main, before the Phase 2 grounding dispatch. Both outputs go into
  Subagent A and Subagent B.

**IMPORTANT**: wrap in `bash -c '...'`. Raw `packages/*/src` globs abort under zsh with
`zsh: no matches found` BEFORE `2>/dev/null` can catch it, silently emptying the map. Use
`find` for layout robustness (`src/`, `lib/`, `source/`).

## Local mode

The default, and the only mode `/fix-pr-review` and `/harden-plan` ever run. Both operate
on the clone where they run.

```bash
# Repo map files: inventory of TS/TSX in shared roots (capped 500 lines, truncation marked)
bash -c '
if [ -d packages ] || [ -d apps ]; then
  { [ -d packages ] && find packages -type f \( -name "*.ts" -o -name "*.tsx" \) \
      -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
      -not -name "*.test.*" -not -name "*.spec.*" 2>/dev/null
    [ -d apps ] && find apps -type f \( -name "*.ts" -o -name "*.tsx" \) \
      -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
      -not -path "*/.next/*" -not -name "*.test.*" -not -name "*.spec.*" 2>/dev/null
  } | awk "NR<=500{print} END{if(NR>500)print \"[truncated at 500 of \" NR \" lines, use Glob directly for ground truth]\"}"
fi
'

# Repo map exports: top-level exports across src/lib/source dirs (capped 500 lines, truncation marked)
bash -c '
if [ -d packages ] || [ -d apps ]; then
  find packages apps 2>/dev/null -type d \( -name src -o -name lib -o -name source \) \
    -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
    -not -path "*/.next/*" 2>/dev/null \
    | xargs -I{} grep -rhnE "^export (default (async )?function|function|const|class|type|interface|async function) \w+" {} 2>/dev/null \
    | awk "NR<=500{print} END{if(NR>500)print \"[truncated at 500 of \" NR \" lines, grep packages/ apps/ directly for more]\"}"
fi
'
```

## Cross-repo mode: `/review-pr` only

`/review-pr` reviews the PR URL it was given, which may live in a repo that is not the cwd.
When Phase 1 set `CROSS_REPO_MODE=true` there is no local tree to scan, so the file list
comes from the API and on-demand fetches cover the export scan:

```bash
if [ "$CROSS_REPO_MODE" = "true" ]; then
  gh api "repos/<owner>/<repo>/git/trees/${CURRENT_HEAD}?recursive=1" \
    --jq '.tree[] | select(.type == "blob" and (.path | test("^(packages|apps)/.*\\.(ts|tsx)$")) and (.path | test("node_modules|dist|build|\\.test\\.|\\.spec\\.") | not)) | .path' \
    | awk 'NR<=500{print} END{if(NR>500)print "[truncated at 500 of " NR " lines]"}'
  repo_map_files="<output>"
  repo_map_exports="N/A (cross-repo mode, fetch via 'gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>' on-demand)"
fi
```

## Stash the outputs

Stash the two outputs as `repo_map_files` and `repo_map_exports`. What to set when neither
`packages/` nor `apps/` exists, and which subagent reroutes its searches in that case, is
stated at each caller. Each skill uses its own fallback.
