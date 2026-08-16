# Fork creation lanes

Loaded from section 6 of `SKILL.md` at the creation-lane freeze, and only when the selected head repository is not the base repository. A same-repository head takes the inline `gh pr create --head <branch>` lane and never reaches this.

A fork owned by the authenticated user uses the supported `<head-owner>:<branch>` form; an organization-owned fork uses GitHub's REST create-pull endpoint with the exact head repository identity and `head_repo` field when required. Determine owner type and the authenticated user's ownership from stable IDs, not name shape; any other ownership relation blocks.

Authenticated-user-owned fork:

```bash
gh pr create --repo "$repository" --base "$base" --head "$head_owner:$head_branch" --title "$title" --body-file "$body_path" [--draft]
```

Organization-owned fork (build exact JSON from the frozen values and record its digest):

```bash
gh api --method POST "repos/$repository/pulls" --input "$create_request_json"
```

The REST request carries exact `title`, `body`, `base`, qualified `head`, `draft`, and the selected head repository identity, including `head_repo` when required.

Section 6 still owns everything around these two commands: the metadata check that the head belongs to the base repository's fork network, the `preflight-mutations` card immediately before creating, the `--draft` rule for the `gh pr create` form, the identical `gh pr view` read-back, and every verification and mismatch disposition after it.
