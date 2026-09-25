# Q6a cross-repo search

Subagent 1 loads this only when `repo_map_exports` is the cross-repo `N/A` marker; STEP A, the local algorithm, and the audit format stay in `q6-reusability-search.md`. There is no local tree here:
`Grep`/`Glob` against `packages/` or `apps/` prove nothing. Phase 1 sets this
marker on every cross-repo run regardless of the local cwd layout, so its
presence is the whole trigger. Run the same three searches against the reviewed
head, never the default branch. Save the RAW recursive tree response first:
its top-level `truncated` flag is the coverage gate, and any projection that
drops the flag cannot certify anything:

```bash
gh api "repos/<owner>/<repo>/git/trees/<head-sha>?recursive=1" > /tmp/q6_tree.json
```

If `jq -r .truncated < /tmp/q6_tree.json` is true, the blob list is partial:
verified findings in fetched blobs still stand, but `No issues` is forbidden,
write `Cannot assess: would need <file>`. Otherwise derive the blob list
locally:

```bash
jq -r '.tree[] | select(.type == "blob" and (.path | test("\\.(ts|tsx)$"))) | .path' /tmp/q6_tree.json > /tmp/q6_tree.txt
```

STEP B searches are content searches: narrow the fetch set by path (same-name
or name-similar first for the exact-name search, then shared roots for the
semantic-root tokens, then the components directories), then fetch each
candidate and grep the exact name and root tokens in its contents. Path
matching alone never authorizes `No issues`.

Paths in that file come from the target repository, so their bytes must never
appear in shell source: a filename containing `$(...)` would execute on paste.
Select candidates by trusted line number only, pipe the bytes to the encoder
over stdin, and pass the encoded endpoint as one quoted argument:

```bash
sed -n '<N>p' /tmp/q6_tree.txt | python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.stdin.read().strip(), safe=""))' > /tmp/q6_encoded.txt
gh api "repos/<owner>/<repo>/contents/$(cat /tmp/q6_encoded.txt)?ref=<head-sha>"
```

The encoded output carries only URL-safe bytes, so the substitution on it is
inert; the raw path never crosses the shell-code boundary.

Coverage contract: a `No issues` result requires every candidate the path
narrowing named to have been fetched, grepped, and verified. Do NOT use
`search/code` as coverage: it indexes the default branch rather than the
reviewed head, skips files over 384 KB, caps at 1,000 results, and can return
`incomplete_results`. Anything unfetched, any failed fetch, or a truncated
tree forces `Cannot assess: would need <file>`. Record each fetch as the audit
entry's tool call.

