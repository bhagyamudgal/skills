# Sweep mode: before claiming the task done

The pre-creation search only sees what you were about to write. It cannot see what was already duplicated, and diff-scoped tools cannot either: `simplify` inspects duplication introduced by the change and explicitly leaves pre-existing code alone. So a handler copied into two apps last month is invisible to every check in the pipeline, forever, unless this sweep runs.

Scope it to every file the task touched plus their siblings, not the diff.

Prefer a real clone detector for copied blocks. `jscpd` does Rabin-Karp fingerprinting over token streams and finds cross-file copies in milliseconds, without you guessing which files to compare, which is the part of a manual sweep that fails silently. If the repo has it wired up, run it; if not, one `npx jscpd@5 <paths> --reporters console` is usually worth it before hand-rolling greps. Use the canonical `jscpd@5`, the official Rust rewrite, shipped as a self-contained native binary through npm, cargo, brew or curl. Not the third-party `jscpd-rs` port, which is a separate project and benchmarks slower.

It will not find the classes below, so still run them: a literal duplicating a named constant, and a fact duplicated between docs and code, are both invisible to token-level detection.

Derive the file set from git rather than typing paths: it respects `.gitignore`, cannot name a directory that does not exist, and skips `node_modules` without a flag.

```bash
BASE=<merge-base or the commit you branched from>
FILES=$(git ls-files 'apps' 'packages' 'src' 2>/dev/null | grep -vE '\.d\.ts$')

# 1. Literals repeated 3+ times: the ones worth naming, or already named
#    somewhere you never searched because a name search cannot find a value.
printf '%s\n' "$FILES" | xargs grep -hoE "['\"][A-Za-z][A-Za-z0-9:._/-]{5,}['\"]" \
  | tr -d "\"'" | sort | uniq -c | sort -rn | awk '$1 >= 3'

# 2. A specific literal you suspect is already an exported constant.
printf '%s\n' "$FILES" | xargs grep -n '"text/html"'

# 3. Facts stated in a comment that already live in the docs. This is the
#    class no clone detector sees, and the one that duplicates fastest when
#    the same change writes the spec section and the comment.
git diff -U0 "$BASE" -- 'apps' 'packages' \
  | grep -E '^\+\s*(//|\*)' | sed 's/^+[[:space:]]*//' \
  | grep -oE '[A-Za-z][A-Za-z ]{28,}' | sed 's/  */ /g; s/^ //; s/ $//' | sort -u \
  | while IFS= read -r phrase; do
      hit=$(grep -rlF "$phrase" docs/ ./*.md 2>/dev/null | head -1)
      [ -n "$hit" ] && printf '  %s -> %s\n' "$phrase" "$hit"
    done
```

Do not hand-roll a check for near-identical function bodies. A grep over declaration lines dedupes on text that contains the name, so two helpers with different names, the case worth finding, can never collide, and the check quietly reports nothing while looking like it ran. Structural similarity needs a clone detector; that is what `jscpd` above is for.

Commands here assume GNU-compatible `grep`. `ugrep`, `busybox` and BSD `grep` differ on bracket classes and `--exclude` ordering, so if a check returns suspiciously zero, verify it finds a planted duplicate before trusting it.

Then ask, per hit:

- Does this fact/behavior have one home, or several that can drift apart?
- If two copies exist and one is fixed, does the other silently stay broken? That is the whole test. A bug fixed in one copy staying broken in the other is the cost; everything else is style.
- For monorepos: check shared packages even if it adds a dependency edge. Duplicating across packages is worse than coupling them.
- If you wrote a new utility, ask: "Could I delete this and import from somewhere else?" If yes, do that instead.

Report the sweep even when it finds nothing. A silent sweep and a skipped sweep are indistinguishable to the person reading your completion report, and only one of them is honest.
