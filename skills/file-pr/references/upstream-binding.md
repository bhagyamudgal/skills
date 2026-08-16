# Binding the branch upstream after the push lands

Loaded from section 6 of `SKILL.md` on an initial publication, immediately after the push read-back and the recheck of the active symbolic ref, branch-ref SHA, and `HEAD` against the frozen attempt. The existing-PR branch never pushes and never reaches this.

Before resolving the branch's current symbolic upstream and SHA, inspect both configuration keys:

```bash
git config --get "branch.<card-branch>.remote"
git config --get "branch.<card-branch>.merge"
```

Both keys authoritatively absent means upstream state `ABSENT` and permits first binding. One key absent, an empty or malformed value, a configured remote/ref that cannot resolve, or any lookup failure other than authoritative absence is `reconcile-required`. A fully configured upstream is an authoritative no-op only when its configured remote equals `<push-remote>`, its symbolic name equals `<push-remote>/<card-branch>`, and its SHA equals **landed-push SHA**. Otherwise preflight a separate binding guarded by the local values, **landed-push SHA**, and that exact configured or `ABSENT` state, then bind and read it back:

```bash
git branch --set-upstream-to="<push-remote>/<card-branch>" "<card-branch>"
git rev-parse --abbrev-ref --symbolic-full-name "<card-branch>@{upstream}"
git rev-parse "<card-branch>@{upstream}"
```

Require the configured remote to equal `<push-remote>`, the symbolic upstream to equal `<push-remote>/<card-branch>`, and its SHA to equal **landed-push SHA**. If binding or read-back fails after the remote push landed, record `remote landed / upstream not bound` with both observed states and continue reconciliation without retrying the push.
