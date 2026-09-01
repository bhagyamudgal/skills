# Republishing to an existing PR

Loaded from section 6 of `SKILL.md`, and only when the card carries an **Existing PR URL**. An initial publication never reaches any of this. Section 6's `$repository` resolution and its **valid remote** definition are already in hand before this branch starts.

Read that exact URL before enumerating remotes; its `headRepository` establishes the required head repository identity:

```bash
gh pr view "$existing_pr_url" --repo "$repository" --json url,title,body,baseRefName,baseRefOid,headRefName,headRefOid,headRepository,state,isDraft
```

Require `headRepository.id` and `nameWithOwner` to be available. Enumerate configured valid remotes and keep only those matching that exact head identity. Auto-select one match; for multiple matches, use AskUserQuestion with concrete `<remote>: <nameWithOwner> (<id>)` options, paginating disjoint option sets when needed; zero matches stops with the exact next action `Configure a remote whose complete endpoint sets resolve to the existing PR head repository, then rerun file-pr.` Freeze the selected remote, revalidate its remote branch at current `HEAD`, and reconcile the PR's base, state, draft mode, head branch, and head SHA against the card and publication request. A mismatch stops or enters `done`'s explicit base-rebind path. Only a separately preflighted title/body edit may mutate it.

On the existing-PR branch, the revalidation at the start of this section supplies the remote-head evidence without another push.

## At section 6's paginated candidate search

When **Existing PR URL** is present, its direct read is the intended attempt; require its head repository ID, head name and SHA, base name, `state`, and `isDraft` to match the selected remote, card, and publication request before reuse.

## On a superseding card

After `done` verifies a superseding card against the observed base, reuse only **Existing PR URL** and preflight any still-required title/body edit as its own exact mutation.
