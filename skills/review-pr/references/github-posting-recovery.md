
# GitHub posting: failure recovery

Main loads this in Phase 4 only when Phase A, B, or C fails. The fresh-review path stays in `${CLAUDE_SKILL_DIR}/references/github-posting.md`, already loaded.

## Step 7: Posting failed recovery (NEVER silent)

If Phase A, B, or C fails: **DO NOT silently collapse to a monolithic body.** The prior silent fallback was the root cause of past zero-resolvable-comment runs.

### Rolling or submitted review exists

If authoritative read-back shows the target review is already submitted, including `ROLLING_PATH=true`, do not enter either cleanup branch below. Preserve the submitted review and query its complete body, line comments, and file-level threads. Reconcile every thread against the frozen canonical file-level entries and classify each entry as exactly one of `landed`, `confirmed-absent`, or `ambiguous`; cache exact landed IDs immediately. A body mismatch, multiple matches, or inconclusive query is `reconcile-required` and blocks further mutation.

When one or more entries are `confirmed-absent`, offer only `Create supplemental review for confirmed-absent threads`, `Abort, leaving the submitted review unchanged`, or `Show payload & preserve review`. The supplemental path refreshes the submitted-review and PR guards, freezes a summary naming the original review plus only the confirmed-absent entries, and invokes `preflight-mutations` with those exact payloads and digests. It then creates a new pending review through Step 4, attaches its file-level entries through Step 5, submits the same `REVIEW_EVENT` through Step 6, and reconciles every result before advancing. Record each new cached thread as owned by the supplemental review; the split ownership makes later rolling reuse ineligible. Abort and show-payload leave the submitted review unchanged. Never attach a thread to a submitted review, delete it, route it through pending cleanup, or replace it with a monolithic review.

### No pending review

When Phase A reconciliation set `NO_PENDING_REVIEW=true`, use a distinct recovery prompt: `Post frozen monolithic review` or `Abort, keep local`. Before a post, refresh the PR guards and invoke `preflight-mutations` with the complete zero-match reconciliation evidence plus the exact frozen monolithic body and digest; then post with `gh pr review <url> "$REVIEW_FLAG" --body-file /tmp/review-pr-<num>-monolithic.md` without calling `cleanup_pending_review`. Reconcile every result by exact author, head, required GitHub state, semantic verdict in the body, and complete body before any retry. Abort performs no mutation. After one exact match, run the monolithic publication write-back below before convergence; this branch ends only after that write-back succeeds or its failure is reported.

### Pending review exists

Use AskUserQuestion (cursor-selectable, NOT a numbered prose list).

**Disclose partial state in the question text**: name which phase failed AND report how many threads/comments are already attached, e.g.:

> "Phase B failed on thread 3 of 8. Pending review `<REVIEW_NODE_ID>` has 2 file-level threads + N line-level comments attached from Phase A. GitHub error: `<error>`. How should I proceed?"

```
Question:
  header: "Post failed"
  text: "<phase>. Pending review has <K> thread(s) attached. Error: <error>. How should I proceed?"
  options:
    - label: "Post as monolithic body"
      description: "Delete the pending review, then post via gh pr review --body-file with all findings inline, which loses resolvable threads but the review still appears on GitHub"
    - label: "Abort, keep local"
      description: "Delete the pending review; nothing is posted. Review stays in your terminal only"
    - label: "Show payload & keep draft"
      description: "Print the failing request body/mutation and leave the pending review as a draft on GitHub for manual submit"
```

Immediately before the chosen recovery's first delete or fallback-post mutation, refresh the PR and pending review. Freeze a canonical pending-review snapshot containing the exact review ID, author, `PENDING` state, head SHA, complete review body, and every attached comment and thread's IDs, path, line, side, and body; digest that snapshot. Invoke `preflight-mutations` with the exact PR and head SHA, the snapshot path and digest, selected recovery action, frozen monolithic body path and digest, and the user's Step 7 choice. Re-fetch and require an exact snapshot match immediately before deletion. Apply the preflight result contract before continuing; a count match is never sufficient.

**Cleanup helper** (used by "Post as monolithic" + "Abort"):

```bash
cleanup_pending_review() {
  local out readback
  out=$(gh api graphql -f query='
    mutation($id: ID!) {
      deletePullRequestReview(input: {pullRequestReviewId: $id}) { clientMutationId }
    }
  ' -f id="$REVIEW_NODE_ID" 2>&1) || true

  readback=$(gh api graphql -f query='
    query($id: ID!) {
      node(id: $id) { ... on PullRequestReview { id state body } }
    }
  ' -f id="$REVIEW_NODE_ID") || return 2

  if echo "$readback" | jq -e '.errors' >/dev/null; then
    echo "Pending review cleanup read-back was inconclusive: $out / $readback" >&2
    return 2
  fi

  if [ "$(echo "$readback" | jq -r '.data.node.id // empty')" != "" ]; then
    echo "Pending review cleanup did not land or changed ambiguously: $out / $readback" >&2
    return 1
  fi
}
```

The cleanup result is authoritative only when the exact pending review node is absent. A surviving node, failed read-back, or changed review remains `reconcile-required`; preserve its IDs and stop without fallback posting.

**On "Post as monolithic"**: require `cleanup_pending_review` to confirm absence, refresh the PR guard, then invoke a new preflight for the exact frozen monolithic body before `gh pr review <url> "$REVIEW_FLAG" --body-file /tmp/review-pr-<num>-monolithic.md`. Reconcile every result by exact author, head, required GitHub state, semantic verdict in the body, and complete body before any retry. After one exact match, run the monolithic publication write-back below before convergence.

**Monolithic publication write-back**: freeze the authoritative match as `publication_evidence` with `publication_mode: monolithic`, the exact review database and node IDs, author, head SHA, GitHub state, verdict, complete-body SHA-256, every surviving finding ID, and verification timestamp. Merge it into `$CACHE_FILE` with `contract_version: REVIEW_CACHE_CONTRACT_VERSION`, `last_posted_review_id`, `last_posted_review_node_id`, `last_posted_verdict`, `last_posted_at`, `last_posted_finding_ids`, and `publication_evidence`; preserve existing `posted_comments` only as historical ownership records because a monolithic review creates no per-finding threads. A later run must not treat those entries as owned by the monolithic review. Follow `references/finding-state-schema.md` "Phase 4: write back" for every surviving finding, then merge the same `publication_evidence` as a top-level `publication` block in `$STATE_FILE`, preserving its `findings` and `convergence` blocks. Write both files atomically. A failed write-back is reported and blocks convergence; publication already landed, so never repost it.

**On "Abort"**: require authoritative cleanup read-back, then stop. Report `reconcile-required` instead of claiming an abort when cleanup is unresolved.

**On "Show payload"**: print the offending JSON/mutation. Do NOT clean up. User explicitly chose to keep the draft. Print the pending review URL.

