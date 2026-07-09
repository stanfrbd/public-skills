# Public Skills

A public collection of reusable skills intended to work with any compatible agent.

## Included skill

- **GitBook API workflows**: read GitBook organizations, spaces, pages, and documents; resolve page paths; and manage page updates through the documented API flow.

## Prerequisites

To use the GitBook skill, you must already have one of the following:

- an organization ID and API token, or
- a specific space, or
- a specific page / page URL.

**Usage note:** the workflow starts from an already identified **space** or **page**. If you only know the organization, resolve the target space first.

## What is included

- a public, agent-neutral skill description
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
- verification of API-supported operations before attempting writes

## Notes

- The public API surface can evolve.
- If an endpoint or payload differs from this copy, prefer the live GitBook API documentation.
