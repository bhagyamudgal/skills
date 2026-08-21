---
name: create-artifact
description: Publish an HTML or Markdown file to a permanent public URL through Netlify's REST API. Use when a plan, report, or page should be a shareable link rather than a local file, or when running outside Claude Code where the Artifact tool is unavailable.
license: MIT
allowed-tools: Bash, Read, Write
---

# Create artifact

Turn a local document into a link. Three authenticated calls, no CLI, no git repository.

The mechanism is one site, many deploys. A Netlify deploy is a full site snapshot, so you never create a site per artifact: the site's main URL always serves the newest one, and every past deploy keeps its own permanent `deploy_url` keyed by deploy id. That is how one site yields unlimited permanent links.

## 1. Preflight

`NETLIFY_AUTH_TOKEN` holds a personal access token and every call sends `Authorization: Bearer $NETLIFY_AUTH_TOKEN`. When it is missing, stop and tell the user to create one under User settings, Applications, Personal access tokens, then export it.

`NETLIFY_ARTIFACT_SITE_ID` names the reused site. When it is missing, create the site once and ask the user to export the returned `id` so later runs share it:

```bash
curl -s -X POST https://api.netlify.com/api/v1/sites \
  -H "Authorization: Bearer $NETLIFY_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"<slug>-artifacts"}' | jq -r .id
```

The token is a credential. Pass it through the environment, keep it out of command echoes, logs, and any URL you print.

**Done when** both values are set and the site id belongs to an account the user controls.

## 2. Build one self-contained HTML page

Publish HTML. How a `.md` file renders depends on the `Content-Type` the host serves, which is not a contract you control, while an HTML page renders anywhere. Convert Markdown yourself rather than adding a converter dependency: write the page directly, with inline CSS and no external requests, so it survives with no network beyond the host.

Write it to a temporary directory as `index.html`. Keep `#` and `?` out of the filename, which Netlify's file paths reject.

**Done when** a single `index.html` exists and opening it locally shows the finished document.

## 3. Deploy in three calls

Digest first. Netlify matches file contents by SHA1 of the exact bytes.

```bash
DIGEST=$(shasum -a 1 index.html | cut -d' ' -f1)

DEPLOY=$(curl -s -X POST \
  "https://api.netlify.com/api/v1/sites/$NETLIFY_ARTIFACT_SITE_ID/deploys" \
  -H "Authorization: Bearer $NETLIFY_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"files\":{\"/index.html\":\"$DIGEST\"}}")

DEPLOY_ID=$(echo "$DEPLOY" | jq -r .id)
```

The response's `required` array lists the digests Netlify still needs. An empty array means it already holds these exact bytes, so skip the upload. Otherwise send the raw file:

```bash
curl -s -X PUT \
  "https://api.netlify.com/api/v1/deploys/$DEPLOY_ID/files/index.html" \
  -H "Authorization: Bearer $NETLIFY_AUTH_TOKEN" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @index.html
```

The digest map keys the path with a leading slash. The upload URL does not.

Then poll `GET /api/v1/deploys/$DEPLOY_ID` until `state` reads `ready`.

**Done when** `state` is `ready`.

## 4. Hand back the link

Report the deploy's `deploy_url`, which is the permanent snapshot of this artifact, and say that the site's main URL now serves it as the newest one.

**Done when** the user has a URL that loads the finished page.

## Publishing is public

A `deploy_url` needs no credentials to read, and anyone holding it can read the document. Publish content written to be read by others. When it carries credentials, customer data, private notes, or unreleased work, ask the user before the deploy call rather than after.
