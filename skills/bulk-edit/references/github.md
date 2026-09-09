# Bulk editing GitHub issues

Concrete costs and commands. Numbers verified on a 638-issue title rewrite, 2026-09-09.

## Rate limit buckets fail independently

`gh api rate_limit -q '.resources | to_entries[] | "\(.key): \(.value.remaining)/\(.value.limit)"'`

| Bucket | Limit | Spent by |
|---|---|---|
| `graphql` | 5000 points/hr | `gh issue view`, `gh issue edit`, `gh project item-list` |
| `search` | **30 requests/min** | `gh issue list` |
| `core` (REST) | 5000/hr | `gh api repos/...` |
| secondary / abuse | undocumented | rapid writes of any kind |

Three traps follow from that table.

**A read-then-write-then-verify loop on `gh issue view` / `gh issue edit` costs 3 GraphQL points per record.** 638 issues exhausted the budget before the run finished. Read the whole population once up front instead, and write through REST.

**`gh issue list` spends the search bucket, not GraphQL.** It is the first thing to fail on a bulk run and it reports the failure as `GraphQL: API rate limit already exceeded`, which points at the wrong bucket. It also serves a lagging index, so it is unsafe for verification regardless of quota.

**The secondary limit is invisible.** After ~638 rapid writes, GraphQL rejected calls while `rate_limit` reported every bucket full. Do not trust `rate_limit` to explain a rejection. It clears on its own within minutes.

## The cheap write path

REST `PATCH` returns the updated object, so the write and its verification are one call:

```bash
gh api -X PATCH repos/OWNER/REPO/issues/N -f 'title=NEW TITLE' -q '.title'
```

Compare the returned value to the intended value. If they match, the write landed and is verified. 638 renames this way consumed about 570 of the 5000 core budget with a 0.4s pause between calls.

Build the argv as a list in Python rather than a shell string. Issue titles contain `&`, `•`, `‣`, `🚨`, `–` and non-breaking spaces, and no quoting layer then has to survive them.

## Reading the population authoritatively

`gh issue list` lags. REST pagination does not, and it excludes pull requests by filtering on the `pull_request` key:

```bash
gh api 'repos/OWNER/REPO/issues?state=all&per_page=100' --paginate \
  --jq '.[]|select(has("pull_request")|not)|{number,title}'
```

About 33 calls for 3300 issues. Use this for both the pre-run snapshot and the post-run verification.

## Recovery is free and permanent

GitHub stores every title change as a `renamed` timeline event holding the full previous string, forever:

```bash
gh api repos/OWNER/REPO/issues/N/timeline --paginate \
  -q '.[]|select(.event=="renamed")|"\(.created_at) \(.actor.login)  from: \(.rename.from)"'
```

Verify this on one real record before classifying the batch as reversible. It also reconstructs the full edit history, which is what section 8 of the skill needs.

## Detecting an automation behind the edits

Cluster the rename events by weekday and hour in the automation's stated timezone:

```python
from datetime import datetime, timezone
import zoneinfo, collections
B = zoneinfo.ZoneInfo('Europe/Berlin')
wd, hr = collections.Counter(), collections.Counter()
for created_at, login in events:
    t = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).astimezone(B)
    wd[t.strftime('%a')] += 1
    hr[t.hour] += 1
```

A weekly job shows up as consecutive same-weekday dates inside a narrow minute band, for example 01:03 to 01:26 across twelve consecutive Thursdays. Human maintenance scatters across weekdays and working hours.

`.actor.type` distinguishes `User` from `Bot`. An automation running under a `User` account uses a personal token, so it will not appear in `.github/workflows/` and cannot be found by reading the repository.

## Project board fields

`gh project item-list N --owner OWNER --format json --limit 4000` returns every item with its field values and a `totalCount`, and it does not truncate silently. It is slow, around three minutes for 3100 items, so run it detached and wait on the file.

Iteration fields return an object, not a string:

```jsonc
"release": { "title": "27.1", "startDate": "2026-09-10", "duration": 7, "iterationId": "..." }
```

Compare against `.release.title`. Reading it as a string raises `AttributeError: 'dict' object has no attribute 'strip'`.

A field duplicated in both a board column and the record's text will drift. Compare the two before assuming the text is authoritative: in the verified run, 209 of 768 issues carried a title token that disagreed with the board field, with the board ahead every time.
