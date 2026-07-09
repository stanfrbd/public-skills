#!/usr/bin/env python
"""Small CLI wrapper around gitbook_api_helpers.py.

Required environment variables:
- GITBOOK_TOKEN
- GITBOOK_ORG_ID

Examples:

    python scripts/gitbook_cli.py verify-auth
    python scripts/gitbook_cli.py list-spaces
    python scripts/gitbook_cli.py page-by-path SPACE_ID docs/getting-started
    python scripts/gitbook_cli.py update-page SPACE_ID PAGE_ID ./content.md --subject "Update docs" --require "Expected text"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gitbook_api_helpers import GitBookClient


def print_json(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="GitBook API helper CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("verify-auth", help="Verify GITBOOK_TOKEN against GitBook")

    list_spaces = sub.add_parser("list-spaces", help="List spaces for an organization")
    list_spaces.add_argument("--org-id", help="Organization ID. Defaults to GITBOOK_ORG_ID.")

    page_by_path = sub.add_parser("page-by-path", help="Resolve a page by GitBook path")
    page_by_path.add_argument("space_id")
    page_by_path.add_argument("page_path")

    get_page = sub.add_parser("get-page", help="Read a page by ID")
    get_page.add_argument("space_id")
    get_page.add_argument("page_id")

    update_page = sub.add_parser("update-page", help="Update a page with Markdown through a change request")
    update_page.add_argument("space_id")
    update_page.add_argument("page_id")
    update_page.add_argument("markdown_file", help="Path to the Markdown file to publish")
    update_page.add_argument("--subject", default="Update page content", help="Change request subject")
    update_page.add_argument("--require", action="append", default=[], help="Substring that must be present after update; can be repeated")
    update_page.add_argument("--forbid", action="append", default=[], help="Substring that must be absent after update; can be repeated")

    insert_page = sub.add_parser("insert-page", help="Create a new page with Markdown through a change request")
    insert_page.add_argument("space_id")
    insert_page.add_argument("title")
    insert_page.add_argument("markdown_file", help="Path to the Markdown file to publish")
    insert_page.add_argument("--subject", default="Create page", help="Change request subject")
    insert_page.add_argument("--parent-page-id", help="Optional parent page ID")
    insert_page.add_argument("--at", type=int, help="Optional insertion index")

    delete_page = sub.add_parser("delete-page", help="Delete a page through a change request")
    delete_page.add_argument("space_id")
    delete_page.add_argument("page_id")
    delete_page.add_argument("--subject", default="Delete page", help="Change request subject")

    args = parser.parse_args()
    try:
        client = GitBookClient()
    except RuntimeError as exc:
        parser.exit(2, f"error: {exc}\n")

    try:
        if args.command == "verify-auth":
            print_json(client.verify_auth())
        elif args.command == "list-spaces":
            spaces = client.list_spaces(args.org_id)
            print_json([
                {
                    "id": space.get("id"),
                    "title": space.get("title") or space.get("name"),
                    "visibility": space.get("visibility"),
                }
                for space in spaces
            ])
        elif args.command == "page-by-path":
            print_json(client.get_page_by_path(args.space_id, args.page_path))
        elif args.command == "get-page":
            print_json(client.get_page(args.space_id, args.page_id))
        elif args.command == "update-page":
            markdown = Path(args.markdown_file).read_text(encoding="utf-8")
            result = client.update_page_markdown(
                space_id=args.space_id,
                page_id=args.page_id,
                markdown=markdown,
                subject=args.subject,
                required_substrings=args.require,
                forbidden_substrings=args.forbid,
            )
            print_json({"change_request_id": result["change_request_id"]})
        elif args.command == "insert-page":
            markdown = Path(args.markdown_file).read_text(encoding="utf-8")
            print_json(client.insert_page_markdown(
                space_id=args.space_id,
                title=args.title,
                markdown=markdown,
                subject=args.subject,
                parent_page_id=args.parent_page_id,
                at=args.at,
            ))
        elif args.command == "delete-page":
            print_json(client.delete_page(args.space_id, args.page_id, args.subject))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
