"""Small GitBook API helpers for agent-neutral GitBook content workflows.

The helper reads credentials from environment variables and never prints secrets.

Required environment variables:
- GITBOOK_TOKEN
- GITBOOK_ORG_ID

Example:

    from gitbook_api_helpers import GitBookClient

    client = GitBookClient()
    print(client.verify_auth())

    page = client.get_page_by_path("SPACE_ID", "folder/page-slug")
    result = client.update_page_markdown(
        space_id="SPACE_ID",
        page_id=page["id"],
        markdown="# Title\n\nUpdated content.\n",
        subject="Update page content",
        required_substrings=["Updated content"],
    )
    print(result["change_request_id"])
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


BASE_URL = "https://api.gitbook.com/v1"


class GitBookAPIError(RuntimeError):
    """Raised for non-2xx GitBook API responses with a redacted message."""


@dataclass
class GitBookClient:
    """Minimal GitBook API client using only the Python standard library."""

    token: str | None = None
    org_id: str | None = None
    base_url: str = BASE_URL
    user_agent: str = "gitbook-api-skill/1.0"

    def __post_init__(self) -> None:
        self.token = self.token or os.getenv("GITBOOK_TOKEN")
        self.org_id = self.org_id or os.getenv("GITBOOK_ORG_ID")
        if not self.token:
            raise RuntimeError("GITBOOK_TOKEN is not set")
        if not self.org_id:
            raise RuntimeError("GITBOOK_ORG_ID is not set")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }

    def call(self, method: str, path: str, body: Any | None = None) -> tuple[int, Any]:
        """Call the GitBook API and return (status, decoded_json)."""
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=self.headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read().decode("utf-8")
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")[:1000]
            raise GitBookAPIError(f"{method} {path} failed: HTTP {exc.code}: {raw}") from exc

    def verify_auth(self) -> dict[str, Any]:
        """Verify Bearer auth without exposing the token."""
        result: dict[str, Any] = {}
        status, org = self.call("GET", f"/orgs/{self.org_id}")
        result["org"] = {
            "status": status,
            "id": org.get("id"),
            "title": org.get("title"),
        }
        status, user = self.call("GET", "/user")
        result["user"] = {
            "status": status,
            "id": user.get("id"),
            "displayName": user.get("displayName"),
        }
        return result

    def list_spaces(self, org_id: str | None = None) -> list[dict[str, Any]]:
        """List spaces for an organization, handling pagination."""
        organization = org_id or self.org_id

        spaces: list[dict[str, Any]] = []
        page: str | None = None
        while True:
            suffix = f"?page={urllib.parse.quote(page)}" if page else ""
            _, payload = self.call("GET", f"/orgs/{organization}/spaces{suffix}")
            items = payload.get("items") or payload.get("data") or []
            if isinstance(items, list):
                spaces.extend(items)
            next_page = payload.get("next", {}).get("page") if isinstance(payload.get("next"), dict) else None
            if not next_page:
                break
            page = next_page
        return spaces

    @staticmethod
    def encode_page_path(page_path: str) -> str:
        """Encode a GitBook content path for /content/path/{pagePath}.

        The full path must be encoded with safe='' so slashes become %2F.
        """
        return urllib.parse.quote(page_path.strip("/"), safe="")

    def get_pages_tree(self, space_id: str) -> dict[str, Any]:
        """Return the page tree for a space."""
        _, tree = self.call("GET", f"/spaces/{space_id}/content/pages")
        return tree

    def get_page_by_path(self, space_id: str, page_path: str) -> dict[str, Any]:
        """Resolve and return a page by path."""
        encoded = self.encode_page_path(page_path)
        _, page = self.call("GET", f"/spaces/{space_id}/content/path/{encoded}")
        return page

    def get_page(self, space_id: str, page_id: str) -> dict[str, Any]:
        """Return one page by ID."""
        _, page = self.call("GET", f"/spaces/{space_id}/content/page/{page_id}")
        return page

    @staticmethod
    def flatten_doc_text(document: Any) -> str:
        """Return all text found in a GitBook native document JSON object."""
        parts: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                text = value.get("text")
                if isinstance(text, str):
                    parts.append(text)
                for leaf in value.get("leaves", []) or []:
                    if isinstance(leaf, dict) and isinstance(leaf.get("text"), str):
                        parts.append(leaf["text"])
                for child in value.get("nodes", []) or []:
                    walk(child)
                for key, child in value.items():
                    if key not in {"nodes", "leaves", "text", "key"}:
                        walk(child)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(document)
        return "".join(parts)

    def create_change_request(self, space_id: str, subject: str) -> str:
        """Create a change request and return its ID."""
        _, cr = self.call("POST", f"/spaces/{space_id}/change-requests", {"subject": subject})
        return cr["id"]

    def apply_changes(self, space_id: str, change_request_id: str, changes: list[dict[str, Any]]) -> None:
        """Apply raw GitBook change operations to a change request."""
        self.call(
            "POST",
            f"/spaces/{space_id}/change-requests/{change_request_id}/content",
            {"changes": changes},
        )

    def merge_change_request(self, space_id: str, change_request_id: str) -> None:
        """Merge a change request."""
        self.call("POST", f"/spaces/{space_id}/change-requests/{change_request_id}/merge", {})

    def update_page_markdown(
        self,
        space_id: str,
        page_id: str,
        markdown: str,
        subject: str,
        required_substrings: list[str] | None = None,
        forbidden_substrings: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update a page via a GitBook change request and verify before/after merge."""
        required_substrings = required_substrings or []
        forbidden_substrings = forbidden_substrings or []

        cr_id = self.create_change_request(space_id, subject)
        self.apply_changes(
            space_id,
            cr_id,
            [
                {
                    "operation": "update_page",
                    "page": page_id,
                    "document": {"markdown": markdown},
                }
            ],
        )

        _, cr_page = self.call("GET", f"/spaces/{space_id}/change-requests/{cr_id}/content/page/{page_id}")
        cr_text = self.flatten_doc_text(cr_page.get("document", {}))
        self._assert_text_checks(cr_text, required_substrings, forbidden_substrings, phase="change request")

        self.merge_change_request(space_id, cr_id)

        final_page = self.get_page(space_id, page_id)
        final_text = self.flatten_doc_text(final_page.get("document", {}))
        self._assert_text_checks(final_text, required_substrings, forbidden_substrings, phase="final page")
        return {"change_request_id": cr_id, "final_page": final_page, "final_text": final_text}

    def insert_page_markdown(
        self,
        space_id: str,
        title: str,
        markdown: str,
        subject: str,
        parent_page_id: str | None = None,
        at: int | None = None,
    ) -> dict[str, Any]:
        """Insert a new page through a change request and merge it."""
        change: dict[str, Any] = {
            "operation": "insert_page",
            "title": title,
            "document": {"markdown": markdown},
        }
        if parent_page_id:
            change["into"] = parent_page_id
        if at is not None:
            change["at"] = at

        cr_id = self.create_change_request(space_id, subject)
        self.apply_changes(space_id, cr_id, [change])
        self.merge_change_request(space_id, cr_id)
        return {"change_request_id": cr_id}

    def delete_page(
        self,
        space_id: str,
        page_id: str,
        subject: str,
    ) -> dict[str, Any]:
        """Delete a page through a change request and merge it."""
        cr_id = self.create_change_request(space_id, subject)
        self.apply_changes(space_id, cr_id, [{"operation": "delete_page", "page": page_id}])
        self.merge_change_request(space_id, cr_id)
        return {"change_request_id": cr_id}

    @staticmethod
    def _assert_text_checks(
        text: str,
        required_substrings: list[str],
        forbidden_substrings: list[str],
        phase: str,
    ) -> None:
        missing = [s for s in required_substrings if s not in text]
        unexpected = [s for s in forbidden_substrings if s in text]
        if missing or unexpected:
            raise AssertionError(
                f"GitBook verification failed in {phase}: "
                f"missing={missing!r}, unexpected={unexpected!r}"
            )
