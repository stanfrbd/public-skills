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
        """Return all text and link URLs found in a GitBook native document JSON object.

        Text leaves, fragment cell text, and inline link URLs (data.ref.url) are all
        included so that required_substrings checks can match either link labels or URLs.
        """
        parts: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                # Inline link: emit the href so URL-based required_substrings work
                obj = value.get("object")
                if obj == "inline" and value.get("type") == "link":
                    url = value.get("data", {}).get("ref", {}).get("url", "")
                    if url:
                        parts.append(url)
                text = value.get("text")
                if isinstance(text, str):
                    parts.append(text)
                for leaf in value.get("leaves", []) or []:
                    if isinstance(leaf, dict) and isinstance(leaf.get("text"), str):
                        parts.append(leaf["text"])
                for child in value.get("nodes", []) or []:
                    walk(child)
                # Walk fragments (used by GitBook database tables)
                for frag in value.get("fragments", []) or []:
                    walk(frag)
                for key, child in value.items():
                    if key not in {"nodes", "leaves", "text", "key", "fragments"}:
                        walk(child)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(document)
        return "".join(parts)

    @staticmethod
    def doc_to_markdown(document: Any) -> str:
        """Convert a GitBook native document JSON object to Markdown.

        Handles the standard block types returned by the GitBook API:
        heading-1/2/3, paragraph, code/code-line, list-unordered/ordered/item,
        and GitBook database tables (records + fragments). Inline marks (bold,
        italic, code) and inline links are preserved.

        Use this when you need to round-trip an existing page through markdown
        for update_page_markdown. Always re-read the page immediately before
        calling this — never use a cached document.

        WARNING: GitBook database tables are rendered as standard Markdown tables.
        Cell content is read from the fragments array keyed by the values map.
        This is accurate but the resulting Markdown table will lose GitBook-native
        table metadata (column widths, view settings, etc.) on the next write.
        For pages with important database tables, prefer appending content to the
        end of the document rather than replacing the full page.
        """

        def render_inline(nodes: Any) -> str:
            parts: list[str] = []
            for n in nodes or []:
                if not isinstance(n, dict):
                    continue
                obj = n.get("object")
                if obj == "text":
                    for leaf in n.get("leaves", []):
                        t = leaf.get("text", "")
                        marks = {m["type"] for m in leaf.get("marks", [])}
                        if "bold" in marks:
                            t = f"**{t}**"
                        if "italic" in marks:
                            t = f"*{t}*"
                        if "code" in marks:
                            t = f"`{t}`"
                        parts.append(t)
                elif obj == "inline" and n.get("type") == "link":
                    url = n.get("data", {}).get("ref", {}).get("url", "")
                    label = render_inline(n.get("nodes", []))
                    parts.append(f"[{label}]({url})")
            return "".join(parts)

        def build_frag_map(table_node: dict) -> dict[str, str]:
            """Build fragment-id → cell-text lookup for a database table node."""
            fmap: dict[str, str] = {}
            for frag in table_node.get("fragments", []):
                fid = frag.get("fragment")
                if fid:
                    cell_parts = [
                        render_inline(block.get("nodes", []))
                        for block in frag.get("nodes", [])
                    ]
                    fmap[fid] = " ".join(cell_parts).strip()
            return fmap

        def render_table(node: dict) -> str:
            data = node.get("data", {})
            defn = data.get("definition", {})
            records_raw = data.get("records", {})
            col_order = data.get("view", {}).get("columns", list(defn.keys()))
            fmap = build_frag_map(node)
            headers = [defn[c]["title"] for c in col_order if c in defn]
            rows = sorted(records_raw.values(), key=lambda r: r.get("orderIndex", ""))
            lines = [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(["---"] * len(headers)) + " |",
            ]
            for row in rows:
                cells = [fmap.get(row.get("values", {}).get(c, ""), "") for c in col_order]
                lines.append("| " + " | ".join(cells) + " |")
            return "\n".join(lines)

        def render_block(node: dict, list_prefix: str = "") -> str:
            t = node.get("type")
            children = node.get("nodes", [])
            if t == "heading-1":
                return "# " + render_inline(children)
            elif t == "heading-2":
                return "## " + render_inline(children)
            elif t == "heading-3":
                return "### " + render_inline(children)
            elif t == "paragraph":
                return render_inline(children)
            elif t == "code":
                lines = [
                    render_inline(c.get("nodes", []))
                    for c in children
                    if c.get("type") == "code-line"
                ]
                return "```\n" + "\n".join(lines) + "\n```"
            elif t == "list-unordered":
                return "\n".join(render_block(i, "- ") for i in children)
            elif t == "list-ordered":
                return "\n".join(render_block(i, f"{n + 1}. ") for n, i in enumerate(children))
            elif t == "list-item":
                result_lines = []
                for i, child in enumerate(children):
                    text = render_block(child)
                    result_lines.append((list_prefix if i == 0 else "  ") + text)
                return "\n".join(result_lines)
            elif t == "table":
                return render_table(node)
            else:
                return render_inline(children)

        md_blocks = []
        for node in (document.get("nodes") or []):
            rendered = render_block(node)
            if rendered.strip():
                md_blocks.append(rendered)
        return "\n\n".join(md_blocks)

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

    def delete_change_request(self, space_id: str, change_request_id: str) -> None:
        """Delete (discard) an open change request without merging it.

        Use this to clean up stale change requests left behind when apply_changes
        or pre-merge verification fails. GitBook change requests are not
        automatically deleted on error.
        """
        self.call("DELETE", f"/spaces/{space_id}/change-requests/{change_request_id}")

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


# Module-level aliases so these can be imported directly:
#   from gitbook_api_helpers import flatten_doc_text, doc_to_markdown
flatten_doc_text = GitBookClient.flatten_doc_text
doc_to_markdown = GitBookClient.doc_to_markdown
