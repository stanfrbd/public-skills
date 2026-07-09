---
name: gitbook-api
description: Work with GitBook organizations, spaces, pages, documents, and documented API-based content updates.
version: 1.1.0
license: MIT
required_environment_variables:
  - GITBOOK_TOKEN
  - GITBOOK_ORG_ID
---

# GitBook API

## Overview

Use this skill to interact with GitBook through its documented public API: list organizations/spaces, resolve page IDs or page paths, read page content, create pages, update pages, delete pages, and verify content changes.

This skill is intentionally agent-neutral. Any agent or automation that can run Python or make HTTP requests can use it.

## Required prerequisites

The following environment variables must be set:

- `GITBOOK_TOKEN`
- `GITBOOK_ORG_ID`

Do not paste the token into prompts, logs, temporary files, Markdown drafts, or code committed to a repository. The helper script reads credentials from the environment.

## Target prerequisite

Before editing content, the user must provide or identify at least one of these:

- a target **space ID**
- a target **page ID**
- a GitBook page URL that includes the target space and page path

If only an organization is known, first list spaces and select the correct target space.

## Included files

- `scripts/gitbook_api_helpers.py` — Python standard-library helper for GitBook API work
- `scripts/gitbook_cli.py` — small CLI wrapper for team usage
- `references/openapi.yaml` — bundled copy of the GitBook OpenAPI specification

The OpenAPI copy is included for convenience and can become outdated. When precision matters, compare it with the live GitBook API documentation.

## Authentication rules

Use:

```http
Authorization: Bearer <GITBOOK_TOKEN>
```

Do **not** use other authorization schemes unless the current official GitBook documentation explicitly requires them.

Recommended auth checks:

- `GET /v1/orgs/{orgId}` using `GITBOOK_ORG_ID`
- `GET /v1/user`

Only report HTTP status and non-sensitive metadata. Never print the token.

## Core read workflow

1. Check that `GITBOOK_TOKEN` and `GITBOOK_ORG_ID` are present without printing their values.
2. Verify organization access with `GET /v1/orgs/{orgId}`.
3. Verify user auth with `GET /v1/user`.
4. List spaces with `GET /v1/orgs/{orgId}/spaces` when needed.
5. Resolve the target page:
   - from the page tree: `GET /v1/spaces/{spaceId}/content/pages`
   - by page ID: `GET /v1/spaces/{spaceId}/content/page/{pageId}`
   - by path: `GET /v1/spaces/{spaceId}/content/path/{pagePath}`
6. For path lookup, encode the **whole page path** with `urllib.parse.quote(path, safe='')`, including `/` characters.
7. Read the current page before any write.

## Write workflow

GitBook public API content writes should go through change requests. Do not guess direct `PUT` or `PATCH` endpoints on pages/documents.

Recommended sequence:

1. Create a change request.
2. Send one or more content changes to the change request.
3. Re-read the page inside the change request when updating existing pages.
4. Verify unique strings before merge.
5. Merge the change request.
6. Re-read the final page and verify unique strings after merge.

Useful endpoints:

- `POST /v1/spaces/{spaceId}/change-requests`
- `POST /v1/spaces/{spaceId}/change-requests/{changeRequestId}/content`
- `GET /v1/spaces/{spaceId}/change-requests/{changeRequestId}/content/page/{pageId}`
- `POST /v1/spaces/{spaceId}/change-requests/{changeRequestId}/merge`
- `GET /v1/spaces/{spaceId}/content/page/{pageId}`

## Supported content operations

### Update an existing page

```json
{
  "changes": [
    {
      "operation": "update_page",
      "page": "PAGE_ID",
      "document": {
        "markdown": "# Title\n\nUpdated content.\n"
      }
    }
  ]
}
```

### Insert a new page

```json
{
  "changes": [
    {
      "operation": "insert_page",
      "title": "New page",
      "into": "PARENT_PAGE_ID",
      "at": 0,
      "document": {
        "markdown": "# New page\n\nContent.\n"
      }
    }
  ]
}
```

Notes:

- `into` is optional; omit it to create the page at the root of the space.
- `at` is optional; omit it to append at the end.

### Delete a page

```json
{
  "changes": [
    {
      "operation": "delete_page",
      "page": "PAGE_ID"
    }
  ]
}
```

## Helper script usage

The helper and CLI use only the Python standard library.

### CLI examples

Run commands from `skills/gitbook-api`:

```bash
export GITBOOK_TOKEN="..."
export GITBOOK_ORG_ID="..."

python3 scripts/gitbook_cli.py verify-auth
python3 scripts/gitbook_cli.py list-spaces
python3 scripts/gitbook_cli.py page-by-path SPACE_ID folder/page-slug
python3 scripts/gitbook_cli.py get-page SPACE_ID PAGE_ID
python3 scripts/gitbook_cli.py update-page SPACE_ID PAGE_ID ./content.md --subject "Update docs" --require "Expected text"
```

### Python examples

```python
import sys
sys.path.insert(0, "skills/gitbook-api/scripts")

from gitbook_api_helpers import GitBookClient

client = GitBookClient()
print(client.verify_auth())

page = client.get_page_by_path("SPACE_ID", "folder/page-slug")
page_id = page["id"]

result = client.update_page_markdown(
    space_id="SPACE_ID",
    page_id=page_id,
    markdown="# Title\n\nUpdated content.\n",
    subject="Update page content",
    required_substrings=["Updated content"],
)

print(result["change_request_id"])
```

For a repository-local script, add the helper directory to `PYTHONPATH` or import it by path from `skills/gitbook-api/scripts`.

## Multi-page update pattern

When updating several related pages:

1. Resolve all target page IDs first.
2. Re-read all current pages before drafting updates.
3. Create one change request for the logical update.
4. Send multiple `update_page` operations in one `changes` array.
5. Verify each page inside the change request.
6. Merge once.
7. Re-read every final page and verify expected strings.

## Verification details

GitBook page reads may return native document JSON rather than Markdown. Do not assume `document.markdown` exists after reading a page.

To verify content, use `GitBookClient.flatten_doc_text(document)` (also importable as `from gitbook_api_helpers import flatten_doc_text`). It extracts all text leaves **and inline link URLs** from the document tree, so `required_substrings` can match either link labels or their `href` values.

**Do not** pass raw URL strings as `required_substrings` if you intend to match link text — check what label the link uses in the page and match that instead if you want to be label-specific.

## Safety rules

- Never print `GITBOOK_TOKEN`.
- Never print `GITBOOK_ORG_ID` unless it is already intended to be shared internally.
- Never commit tokens or generated files containing tokens.
- Always use the Bearer authorization scheme with the token value from `GITBOOK_TOKEN`.
- Always identify the exact target space/page before writing.
- Always re-read the current page immediately before editing.
- Do not regenerate from an old local draft if a human may have edited the page since the draft was made.
- Apply the smallest targeted change when modifying an existing page.
- Use one atomic change request for related multi-page edits.
- Always verify through API reads after merge.

## GitBook database tables

GitBook pages may contain a native **database table** block type that is distinct from standard Markdown tables. These blocks appear in GET responses with `"type": "table"` and carry their data in a `data` object with `records`, `definition`, and a `fragments` array — not in the `nodes` tree.

Key facts:

- Sending the raw native document JSON back in an `update_page` change operation returns **HTTP 422**. The `document` field in change operations only accepts `{"markdown": "..."}`.
- When doing a full-page markdown round-trip, use `GitBookClient.doc_to_markdown(document)` (also importable as `from gitbook_api_helpers import doc_to_markdown`). It reads the `fragments` array, keys cells by the `values` map in each record, and renders them as standard Markdown tables.
- The round-trip loses GitBook-native table metadata (column widths, view settings). For pages with important database tables, **prefer appending content** rather than replacing the full page.
- To append content without touching existing blocks: reconstruct the full page with `doc_to_markdown`, append your new Markdown, and push via `update_page_markdown`. Always re-read the page immediately before calling `doc_to_markdown` — never use a cached document.

## Low-level API calls

For requests not covered by the high-level helpers, use `client.call(method, path, body)`:

```python
status, data = client.call("GET", f"/spaces/{space_id}/change-requests")
status, cr   = client.call("POST", f"/spaces/{space_id}/change-requests", {"subject": "My CR"})
```

The method returns `(http_status_code, decoded_json)` and raises `GitBookAPIError` on non-2xx responses.

## Stale change requests

When `apply_changes` or pre-merge verification fails, the change request is left open — it is **not** automatically deleted. Stale change requests accumulate in GitBook and clutter the review UI.

Clean up a stale change request:

```python
client.delete_change_request(space_id, cr_id)
```

Or discard it from the GitBook UI. Creating a new change request for a retry is always safe; the stale one does not block subsequent merges.

## Common pitfalls

- Direct writes such as `PUT/PATCH /spaces/{spaceId}/content/page/{pageId}` may fail with `405 method not supported`; use change requests instead.
- `permissions.edit=true` does not by itself prove that a guessed write endpoint exists.
- `/v1/orgs/{orgId}/...` is the organization endpoint family used by these workflows; do not assume `/v1/organizations/{orgId}/...` is equivalent.
- For `content/path/{pagePath}`, encode the full path with `quote(path, safe='')`; otherwise paths containing `/` can fail.
- Page title/navigation metadata and page body content are distinct concepts.
- A page can exist but contain an empty document; always inspect the returned document.
- **Do not** pass the native document JSON (from a GET response) as the `document` field in an `update_page` change operation — the API rejects it with HTTP 422. Only `{"markdown": "..."}` is accepted.
- `flatten_doc_text` and `doc_to_markdown` are static methods on `GitBookClient` but are also exported as module-level functions. Import them directly (`from gitbook_api_helpers import flatten_doc_text`) or call them as `GitBookClient.flatten_doc_text(doc)`. Do **not** try to import them without the class prefix from an older version of the helper.
- GitBook API behavior and schemas may evolve; re-check the OpenAPI spec if an endpoint or payload stops working.

## Quick checklist

- [ ] `GITBOOK_TOKEN` exists and was not printed
- [ ] `GITBOOK_ORG_ID` exists and was not printed
- [ ] organization access verified through `GET /v1/orgs/{orgId}`
- [ ] user auth verified through `GET /v1/user`
- [ ] target space ID confirmed
- [ ] target page ID or path confirmed
- [ ] current page re-read before editing
- [ ] change request created
- [ ] change operations applied
- [ ] change-request content verified when updating pages
- [ ] change request merged
- [ ] final page re-read and verified
