# Board queries

GitHub Projects v2 recipes for this skill. Substitute the project number, owner and field IDs; nothing here is specific to one project. `<OWNER>/<REPO>` is per issue rather than per run, because a board can span repositories.

Every paged selection below carries a `first:` ceiling, and a run whose data exceeds one is silently short. Three are asserted explicitly: the field count against `fields(first:50)`, the item count against `totalCount`, and each item's `fieldValues(first:30)` against the `totalCount` selected on that same connection.

The third matters most, because a truncated `fieldValues` makes a landed write look absent and turns into a spurious `failed`. It applies to the two GraphQL selections only, the fallback loop and the read-back. `gh project item-list` returns no `fieldValues` connection at all; it flattens each field into its own named key, so there is no ceiling to breach on the preferred path. Define the check once and call it where each of those two files is finished, never before one exists:

```bash
assert_field_values() {
  [ -s "$1" ] || { echo "assert_field_values: $1 missing or empty" >&2; return 2; }
  BAD=$(jq -r 'select(type != "object" or (.fieldValues.totalCount | type) != "number")
               | (.id // "unidentified")' "$1") || {
    echo "assert_field_values: cannot parse $1" >&2; return 2; }
  [ -z "$BAD" ] || { echo "assert_field_values: no readable totalCount on: $BAD" >&2; return 2; }
  OVER=$(jq -r 'select(.fieldValues.totalCount > 30) | .id' "$1")
  [ -z "$OVER" ] || { echo "fieldValues truncated for: $OVER" >&2; return 1; }
}
```

Three outcomes, not two. **0** clean, **1** truncated, **2** the input cannot answer the question: missing, empty, unparseable, or carrying a row with no readable `fieldValues.totalCount`. That last case is why the shape is validated before the ceiling is tested. `nodes(ids:)` returns a bare `null` for an id it cannot resolve, and a predicate on a null row is simply false, so a row nobody read would otherwise pass as clean and its unread write would be recorded `failed` rather than `reconcile-required`. Collapsing 2 into either of the others is the trap here: a bare `jq -e` exits non-zero both when nothing is truncated and when the file does not exist, so treating every non-zero as clean lets absent data through the gate, while treating it as truncated stops a healthy run. On **2** the affected rows take `reconcile-required`, because nothing may be classified from data that was never read. The remaining ceilings (`labels(first:50)`, `assignees(first:20)`, `issueTypes(first:20)`) are judged safe only while the project stays under them; check that assumption on a new board.

## Resolve which board

**A board is an owner plus a number, never a number alone.** Project numbers restart per owner, so `12` names a different board under every account. An argument must therefore carry both, or be a URL that yields both. Parse the URL before any lookup, since `gh project view` takes a number and not a URL:

```bash
resolve_board_arg() {
  RAW=$1; ARG=${RAW%%[?#]*}
  case "$ARG" in
    https://github.com/orgs/*/projects/*|https://github.com/users/*/projects/*)
      OWNER=$(printf '%s' "$ARG" | awk -F/ '{print $5}')
      NUMBER=$(printf '%s' "$ARG" | awk -F/ '{print $7}') ;;
    */*) OWNER=${ARG%%/*}; NUMBER=${ARG#*/} ;;
    *) echo "need <owner>/<number> or a project URL, got '$RAW'" >&2; return 1 ;;
  esac
  case $NUMBER in ""|*[!0-9]*) echo "project number not numeric: '$NUMBER'" >&2; return 1 ;; esac
  [ -n "$OWNER" ] || { echo "no owner in '$RAW'" >&2; return 1; }
}
```

Three details carry the weight. **Strip the query and fragment first**, because the URL people actually copy from the address bar carries one: without `${RAW%%[?#]*}`, digit-scraping turns `.../projects/12?view=3` into project `123` and writes to a board nobody named. **Require the number to be all digits**, so a malformed argument stops rather than reaching a lookup. **Reject a bare number outright**, since project numbers restart per owner and there is no safe default; `gh project view 12` without `--owner` refuses anyway when it is not attached to a terminal, reporting `owner is required when not running interactively`, and the skill should fail at the same point rather than one call later.

Ask for the owner rather than picking one.

With no argument, ask the repository which boards it is linked to and keep the open ones. **Page the connection to the end.** `projectsV2(first:20)` returns one page, and a board on a later page is invisible to the one-versus-many decision, which is how a run auto-selects a sole first-page result and writes everywhere except where it meant to:

```bash
CUR=""; : > /tmp/boards.tsv
while : ; do
  [ -z "$CUR" ] && AF=null || AF="\"$CUR\""
  R=$(gh api graphql -f query="{repository(owner:\"<OWNER>\",name:\"<REPO>\"){projectsV2(first:20, after:$AF){totalCount pageInfo{hasNextPage endCursor} nodes{id number title closed}}}}")
  printf '%s' "$R" | jq -e '.data.repository.projectsV2.nodes' >/dev/null || { echo "board listing failed" >&2; exit 1; }
  printf '%s' "$R" | jq -r '.data.repository.projectsV2.nodes[] | [.number,.title,.id,.closed] | @tsv' >> /tmp/boards.tsv
  [ "$(printf '%s' "$R" | jq -r '.data.repository.projectsV2.pageInfo.hasNextPage')" = true ] || break
  CUR=$(printf '%s' "$R" | jq -r '.data.repository.projectsV2.pageInfo.endCursor')
  TOTAL=$(printf '%s' "$R" | jq -r '.data.repository.projectsV2.totalCount')
done
[ "$(wc -l < /tmp/boards.tsv)" -eq "${TOTAL:-$(wc -l < /tmp/boards.tsv)}" ] || { echo "short board listing" >&2; exit 1; }
awk -F'\t' '$4=="false"' /tmp/boards.tsv
```

One open row means one candidate. Several means ask, quoting the number and title of each. Expect several: a repository commonly carries a task board alongside a team or planning board, and picking the first would write to the wrong one.

When a board is owned by the organization and linked to no repository, that query returns nothing. Fall back to the owner's list, which is usually long enough that the number has to come from the requester:

```bash
gh project list --owner <OWNER> --format json | jq -r '.projects[] | select(.closed | not) | "\(.number)\t\(.title)"'
```

Resolve the chosen number to its node ID before anything else, since every query below keys on it:

```bash
gh project view <NUMBER> --owner <OWNER> --format json | jq -r '.id'
```

## Resolve the concepts

Every field, its type, and its options. Completed iterations sit in a separate list from live ones, so a scope argument naming a past release needs both.

```bash
gh api graphql -f query='{node(id:"<PROJECT_ID>"){... on ProjectV2{fields(first:50){nodes{
  ... on ProjectV2FieldCommon{id name dataType}
  ... on ProjectV2SingleSelectField{id name options{id name}}
  ... on ProjectV2IterationField{id name configuration{
      iterations{id title startDate duration}
      completedIterations{id title startDate duration}}}
}}}}}'
```

Assert the returned field count is below 50 before trusting it.

Issue types come from the organization, not the project:

```bash
gh api graphql -f query='{organization(login:"<ORG>"){issueTypes(first:20){nodes{id name}}}}'
```

The login of the credential this run is authenticated as:

```bash
gh api graphql -f query='{viewer{login}}'
```

That is the token's principal, not automatically the person whose sole assignments define the scope. The section 1 gate is satisfied only once this login is confirmed to be the requester's. A bot or shared service credential stops the run rather than silently applying the ownership boundary to somebody else.

Every block below writes under one `$WORK`, a temporary directory that is never the repository being triaged. Create it first:

```bash
WORK=$(mktemp -d); echo "$WORK"
```

**A runner that starts a fresh shell per block will not carry `$WORK` across.** The Claude Code Bash tool is one such runner: working directory persists, shell variables do not. So either substitute the printed path literally wherever `$WORK` appears, or re-assign it at the top of each block. Every block below opens with a guard so an unset `$WORK` fails loudly instead of writing to the filesystem root:

```bash
: "${WORK:?set WORK to the directory printed above}"
```

Labels come from the repository. Check **both** before creating either, because `gh label create` fails on one that already exists. `gh label list` defaults to 30 results, so raise it rather than trusting the default:

```bash
create_label() {
  gh label list --repo <OWNER>/<REPO> --limit 200 --json name -q '.[].name' | grep -qx "$1" && return 0
  gh label create "$1" --repo <OWNER>/<REPO> --color "$2" --description "$3" 2>&1 | tee -a "$WORK/writes.log"
}
create_label agent-ready 0E8A16 "An agent can close this unaided"
create_label need-human  D93F0B "Needs a human decision, spec, or approval"
```

## Enumerate every item

Prefer `gh project item-list`. One call returns each item's `content.body`, `labels`, `assignees`, and `content.type`, which is what the triage step reads.

It does **not** return two things the scope step keys on, so resolve both explicitly:

- **Issue state.** `content` carries `body`, `number`, `repository`, `title`, `type` and `url`, and no open or closed flag. Filter with `--query "is:issue is:open"`, or confirm state from the issue itself.
- **The iteration's live state.** Items carry the release, but treat only its title as reliable. Join that title against the `iterations` list returned by the field-resolution query above. That list holds the running iteration and every future one, which is exactly the default scope. `completedIterations` is a separate list and is reachable only by naming a release explicitly.

Two more gaps block the **write** step rather than the scope step, so close them before building any card:

- **The issue node ID.** item-list gives the project item `id` and `content.number`, never `content.id`. The `updateIssue` call below needs the issue node ID, and the item ID will not be accepted.
- **The current issue type.** item-list returns no issue type, so the ledger's `Current` column for that row cannot be filled from this path.

Both come from the aliased issue query in the read-back section, which therefore runs **twice**: once during scope resolution to supply the node ID and the current type before any card is built, and again after the writes as the labels read-back. Taking the fallback loop instead supplies both inline, since it selects them directly.

```bash
: "${WORK:?set WORK first}"
gh project item-list <NUMBER> --owner <OWNER> --limit 5000 --format json > "$WORK/items.json"
python3 - "$WORK/items.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
got, total = len(d["items"]), d["totalCount"]
print(f"{got} of {total}")
sys.exit(0 if got == total else 1)
PY
```

**The assertion is the point, not the limit.** A default invocation returns 30 items and reports `"totalCount": 3086` in the same object, so a short read announces itself to anyone who compares the two. A large `--limit` can also fail outright against GraphQL's query cost ceiling, reported as `API rate limit exceeded` even when the request-count budget is untouched. Both cases fail the assertion, and both mean fall through to the loop below.

Drop pull requests and draft items before counting anything. `content.type` is `"Issue"` for a real issue; a pull request or draft yields another value or an empty object.

The GraphQL loop is the fallback. It needs `body`, `labels`, and the iteration `startDate` explicitly, and it must stop on an API error rather than treating one as the end of the data:

```bash
: "${WORK:?set WORK first}"
CURSOR=""; : > "$WORK/items.jsonl"
while : ; do
  [ -z "$CURSOR" ] && AFTER=null || AFTER="\"$CURSOR\""
  RESP=$(gh api graphql -f query="{node(id:\"<PROJECT_ID>\"){... on ProjectV2{items(first:100, after:$AFTER){
    pageInfo{hasNextPage endCursor}
    nodes{id content{__typename ... on Issue{id number title body state issueType{name}
      repository{nameWithOwner}
      labels(first:50){nodes{name}} assignees(first:20){nodes{login}}}}
    fieldValues(first:30){totalCount nodes{
      ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}}
      ... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2FieldCommon{name}}}
      ... on ProjectV2ItemFieldIterationValue{title startDate field{... on ProjectV2FieldCommon{name}}}}}}}}}}")
  printf '%s' "$RESP" | jq -e '.data.node.items.nodes' >/dev/null || { echo "page failed, stopping" >&2; exit 1; }
  printf '%s' "$RESP" | jq -r '.errors[]? | "  node error: \(.type // "?") \(.path // [] | join("."))"' >&2
  printf '%s' "$RESP" | jq -c '.data.node.items.nodes[]' >> "$WORK/items.jsonl"
  [ "$(printf '%s' "$RESP" | jq -r '.data.node.items.pageInfo.hasNextPage')" = true ] || break
  CURSOR=$(printf '%s' "$RESP" | jq -r '.data.node.items.pageInfo.endCursor')
done
```

The command's own exit status is deliberately not tested. `gh api graphql` exits 1 whenever the response carries an `errors` key, **even when `data` is fully populated**, so `|| exit 1` here would abort on the partial-data case this section exists to survive. The `jq -e` guard covers every hard failure instead: no output at all exits 4, a null node exits 1, and an empty node list exits 0.

Stop on a **page-level** failure, where `.data.node.items.nodes` is absent. Without that check the page appends nothing, `hasNextPage` reads `null`, the loop breaks, and the run ends at exit 0 with a short file, which is the same undercount this section exists to prevent.

Do not stop on the mere presence of `errors`. A board carrying items from a repository the viewer cannot read returns valid nodes **alongside** a `FORBIDDEN` entry, and a cross-repo board is exactly when this fallback runs. Record those per-node errors and keep the rows that resolved.

`repository{nameWithOwner}` is not optional. A board can hold issues from several repositories, and an issue number is only unique within one, so a number paired with the wrong owner and repository edits a different issue that happens to share it. Every `<OWNER>/<REPO>` below is the issue's own, never a single value fixed for the run: the two labels are resolved and created once per repository represented in the candidate set, and the aliased read-back is issued once per repository.

`content{__typename}` is what separates an issue from a pull request or a draft on this path. Both non-issues return an empty `... on Issue` selection, so without the typename an exclusion cannot state its reason.

Assert the field-value ceiling once the file is complete, after the loop rather than inside it:

```bash
assert_field_values "$WORK/items.jsonl"
```

`$WORK` is a temporary directory, never the repository being triaged.

## Write

Board fields, one item and one field per call. Tee every response to a log, because a malformed value fails a single row in the middle of a run that otherwise looks clean:

```bash
gh api graphql -f query='mutation{updateProjectV2ItemFieldValue(input:{projectId:"<PROJECT_ID>",itemId:"<ITEM_ID>",fieldId:"<FIELD_ID>",value:{singleSelectOptionId:"<OPTION_ID>"}}){projectV2Item{id}}}' 2>&1 | tee -a "$WORK/writes.log"
gh api graphql -f query='mutation{updateProjectV2ItemFieldValue(input:{projectId:"<PROJECT_ID>",itemId:"<ITEM_ID>",fieldId:"<FIELD_ID>",value:{number:3}}){projectV2Item{id}}}' 2>&1 | tee -a "$WORK/writes.log"
```

Issue type is a different mutation, on the issue node rather than the board item:

```bash
gh api graphql -f query='mutation{updateIssue(input:{id:"<ISSUE_NODE_ID>",issueTypeId:"<TYPE_ID>"}){issue{id}}}' 2>&1 | tee -a "$WORK/writes.log"
```

Labels are additive, and the opposite label has to come off in the same call. A verdict that flipped between runs otherwise leaves the issue carrying both, at which point neither means anything:

```bash
gh issue edit <N> --repo <OWNER>/<REPO> --add-label agent-ready --remove-label need-human 2>&1 | tee -a "$WORK/writes.log"
```

Do not reach for `updateIssue(labelIds:)`. That input **replaces** the whole label set, so it silently drops every unrelated label the issue carries.

Then read the log for failures, all of it rather than its tail. Prove the log exists first, because `grep` on a missing file also exits non-zero and would otherwise read as a clean run:

```bash
: "${WORK:?set WORK first}"
test -s "$WORK/writes.log" || { echo "no write log: nothing was attempted" >&2; exit 1; }
grep -icE 'error|malformed|not found|denied' "$WORK/writes.log"
```

A count of `0` is the clean result. A non-zero count names how many rows to inspect.

A non-numeric value into a number field fails one row with `Expected type 'number', but it was malformed`.

Each pipeline ends in `tee`, so it reports `tee`'s exit status and not `gh`'s. That is why the grep is the detection mechanism rather than a second line of defense. `grep -c` still exits 1 on zero matches, so under `set -e` capture the count rather than running it bare.

## Read back

**A board mutation can report success without persisting.** The response carries a normal payload and no `errors` key while the field stays unchanged. Re-read and diff every field; a zero exit code is not evidence.

Board items, batched by node ID. `nodes(ids:)` accepts at most 100. Select the issue's own `id` as well as its `number`: `updateIssue` keys on that node ID, and the project item's `id` is a different identifier that it will not accept. The iteration fragment is required: without it the release value returns as an empty object and the concurrent-editor check below silently sees nothing.

```bash
gh api graphql -f query='{nodes(ids:["<ITEM_ID_1>","<ITEM_ID_2>"]){... on ProjectV2Item{
  content{... on Issue{id number issueType{name}}}
  fieldValues(first:30){totalCount nodes{
    ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}}
    ... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2FieldCommon{name}}}
    ... on ProjectV2ItemFieldIterationValue{title startDate field{... on ProjectV2FieldCommon{name}}}}}}}}' > "$WORK/readback.json"
jq -c '.data.nodes[]' "$WORK/readback.json" > "$WORK/readback.jsonl"
assert_field_values "$WORK/readback.jsonl"
```

Run `assert_field_values` on the response before the field-by-field diff, not only on the enumeration. A board carrying more than thirty fields truncates here too, and an unread value is indistinguishable from an unwritten one, so the row would take `failed` for a write that persisted. On a non-zero result the affected rows take `reconcile-required` instead, which section 6 forbids retrying until an authoritative query settles them.

**Read labels from the issue object, never from `gh issue list`.** Its label-filtered path is search-backed and caps at 1000 results, so on a repository with more matches it returns a short set with no warning, and it can disagree with a direct read of the same issue in the same second. Batch aliased issue reads, forty per call:

```bash
gh api graphql -f query='{repository(owner:"<OWNER>",name:"<REPO>"){
  a1: issue(number:101){id number issueType{name} labels(first:50){nodes{name}}}
  a2: issue(number:102){id number issueType{name} labels(first:50){nodes{name}}}}}'
```

`id` and `issueType{name}` are here because the same query serves the scope step. Run it once before any card is built, to supply the issue node ID the type mutation needs and the current type the ledger's `Current` column records, and once after the writes as the labels read-back. Issue numbers are unique only within a repository, so group the candidates by `repository.nameWithOwner` and issue one call per repository rather than one call for the board.

A number that does not exist returns a `NOT_FOUND` entry under `errors` **alongside** valid data for every other alias. Read `.data` for the aliases that resolved rather than discarding the whole response on the presence of an `errors` key.

## Detecting a concurrent editor

Re-read the release or iteration field alongside the values written, which is why the iteration fragment belongs in the read-back query. A ticket that moved release, or a value that differs from what was measured and written, means somebody edited the board during the run. Report both values and leave theirs in place.
