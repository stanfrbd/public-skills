---
name: gitbook-api
description: Work with GitBook organizations, spaces, pages, documents, and documented API-based content updates.
version: 1.0.0
license: MIT
---

# GitBook API

## Overview

Use this skill when you need to interact with GitBook through its documented API: listing organizations, discovering spaces, resolving page IDs or page paths, reading page content, and creating change requests for content updates.

This skill is intentionally generic and suitable for any agent or automation that can make HTTP requests.

## Prerequisites

Before using the workflow, you must already know at least one of these:

- a target **space**
- a target **page**
- a GitBook page URL that includes the space and page location

If you only know the organization, resolve the relevant space first.

Typical inputs:

- API token
- organization ID
- space ID
- page ID or page path

## Source of truth

Always verify behavior against the live GitBook OpenAPI specification.

A copy of the current spec is included in this repository for convenience, but it can become outdated as the API evolves.

## Core read workflow

### 1) Resolve the organization

If needed, confirm access to the organization before going deeper.

### 2) List spaces

Use the organization spaces endpoint to enumerate available spaces.

### 3) Resolve the target page

If you have a page URL or page path, map it to a concrete page ID inside the correct space.

Useful patterns:

- enumerate the page tree for the space
- resolve a page by path when available
- fetch the concrete page document once the page ID is known

## Write workflow

For content updates, prefer the documented change-request flow rather than guessing a direct page write endpoint.

Recommended sequence:

1. create a change request in the target space
2. add the content update to the change request
3. inspect the draft content if needed
4. merge the change request
5. verify the resulting page content

## Practical rule

Do not attempt a content update until the target space or page is already identified.

The intended starting point is always a known **space** or **page**.

## What to verify

- the token works for the target organization or space
- the space is the correct one
- the page ID or page path resolves correctly
- the endpoint is documented in the current OpenAPI spec
- the intended write path is supported by GitBook change requests

## Notes on API drift

The GitBook API may change over time.

If this document or the bundled OpenAPI copy does not match the live API, update the repository documentation and re-verify the workflow before using it operationally.

## References

- Bundled OpenAPI copy included in this repository
