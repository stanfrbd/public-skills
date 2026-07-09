# Public Skills

A public collection of reusable skills intended to work with any compatible agent.

## Included skill

- **GitBook API workflows**: read GitBook organizations, spaces, pages, and documents; resolve page paths; and manage page updates through the documented change-request API flow.

## GitBook prerequisites

To use the GitBook skill, these environment variables must already be set:

- `GITBOOK_TOKEN`
- `GITBOOK_ORG_ID`

You also need one of the following targets:

- an organization ID to discover spaces
- a specific space ID
- a specific page ID
- a GitBook page URL / page path

**Usage note:** content work starts from an already identified **space** or **page**. If you only know the organization, resolve the target space first.

## What is included

- a public, agent-neutral GitBook skill description
- Python standard-library helper scripts:
  - `gitbook_api_helpers.py` for reusable Python automation
  - `gitbook_cli.py` for command-line use by team members
  - reads `GITBOOK_TOKEN` from the environment
  - verifies auth
  - lists spaces
  - resolves pages by path
  - updates pages through change requests
  - inserts pages
  - deletes pages
  - verifies content after merge
- a local copy of the GitBook OpenAPI specification
- guidance for read operations and change-request-based writes

## Documentation policy

- The OpenAPI specification is copied from the current GitBook public API and may change over time.
- Always verify the live API documentation when precision matters.
- This repository intentionally avoids references to any specific assistant, runtime, or environment-specific details.

## Scope

The GitBook skill covers:

- organization and space discovery
- page and document lookup
- page path resolution
- change requests for content updates
- page creation and deletion through change requests
- verification of API-supported operations before attempting writes
- post-merge API verification

## Quick start

```bash
export GITBOOK_TOKEN="..."
export GITBOOK_ORG_ID="..."

cd skills/gitbook-api
python3 scripts/gitbook_cli.py verify-auth
python3 scripts/gitbook_cli.py list-spaces
```

Python usage:

```python
import sys
sys.path.insert(0, "skills/gitbook-api/scripts")

from gitbook_api_helpers import GitBookClient

client = GitBookClient()
print(client.verify_auth())
```

See `skills/gitbook-api/SKILL.md` for the full workflow.

## Notes

- The public API surface can evolve.
- If an endpoint or payload differs from this copy, prefer the live GitBook API documentation.
- Never commit or print API tokens.
