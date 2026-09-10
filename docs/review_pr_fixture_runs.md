# Paired review-pr fixture runs

How to measure a review-pr skill change end to end: run the old and new skill
against the same diffs, compare finding sets and live cost, and close the
throwaway PRs. This is the live half of bhagyamudgal/skills#60; the static
half is `python3 tools/eval/review_pr_load.py`.

## Fixtures

Three diffs in `hexleap/folslate`, the private monorepo where review-pr
already runs. One per routing path:

- small: under 100 changed lines (solo-main path)
- medium: 100 to 500 lines (parallel-standard path)
- large: over 500 lines (parallel-chunked path). PR 100
  (`bhagya/feat-93-web-manager`, 3805 additions across 18 files) served as
  the large fixture for the baseline.

## Duplicate PRs

Each fixture diff is pushed as two branches and opened as two PRs, one per
skill variant, so neither run sees the other run's review threads. Threads
from variant A would otherwise suppress variant B's matching findings through
the prior-review timeline, and the comparison would measure dedupe instead of
the skill change.

```bash
OWNER=hexleap
REPO=folslate
BASE=bhagya/docs-93-account-ui-scope   # the fixture's real base
HEAD=47efd8a98c3969d1b9907e0986010e14efabbf49

for V in old new; do
  git fetch origin $HEAD
  git checkout -b fixture/pr100-$V $HEAD
  git push -u origin fixture/pr100-$V
  gh pr create --repo $OWNER/$REPO --base $BASE --head fixture/pr100-$V \
    --title "fixture: account UI manager ($V variant, do not merge)" \
    --body "Throwaway duplicate of #100 for the review-pr paired run. Close, do not merge."
done
```

## Collecting transcripts

Run each variant with stream-json logging, one file per agent. Subagent
tokens never appear in the main transcript, so a single log undercounts the
run by every reviewer dispatched. Save the main transcript plus one file per
subagent the run reports in its Phase 4 header.

```bash
claude -p "/review-pr https://github.com/$OWNER/$REPO/pull/<N>" \
  --output-format stream-json --verbose \
  --tee main-old.jsonl
# repeat for the new variant -> main-new.jsonl, plus each subagent log
python3 tools/eval/review_pr_tokens.py main-old.jsonl sub-*.jsonl
python3 tools/eval/review_pr_tokens.py main-new.jsonl sub-*.jsonl --json
```

## Comparing

- Finding sets match on file, rule class, and severity. Every fenced prompt
  block, emitted field, threshold, severity ladder, finding ID formula, and
  marker comment stays byte-identical, and the verifier stays green. Any
  difference gets explained one by one; an unexplained difference blocks the
  skill change.
- Static before/after comes from `tools/eval/review_pr_load.py --json` on
  each variant. Every cell goes down or stays flat.
- Live before/after is tokens and wall time per fixture pair from the parser
  above, plus the Timing block each run prints.

## Cleanup

```bash
gh pr close <old-N> --repo $OWNER/$REPO
gh pr close <new-N> --repo $OWNER/$REPO
git push origin --delete fixture/pr100-old fixture/pr100-new
```

Closing, not merging: the branches exist only to host the diff. The local
review-state files (`~/.claude/review-state/hexleap__folslate__*.yml`) and
cache entries for the fixture PR numbers are scratch; delete them so a later
pair starts at round 1.
