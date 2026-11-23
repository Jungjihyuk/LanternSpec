"""Notion adapter — the same four questions over the Notion REST API (stdlib only).

lantern.yaml:
    knowledge:
      type: notion
      path: <parent page id>      # where approved notes are created
      token_env: NOTION_TOKEN     # (optional) env var holding the integration token

The integration only sees pages shared with it; we never edit existing pages.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from ...core.messages import msg
from . import Adapter, Hit, KnowledgeError

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
MAX_DEPTH = 6  # how many levels of blocks inside blocks one read goes down
MAX_REQUESTS = 100  # most block requests one read makes (Notion answers about three a second)
RETRIES = 3  # how many times a rate-limited (429) request is tried again
_NO_LINE = ("table_of_contents", "breadcrumb")  # blocks that hold no text of their own
_OTHER_DOCUMENT = {"child_page": "[Subpage] {title} ({id})", "child_database": "[Database] {title} ({id})"}  # named, not followed


def _plain(rich: list[dict[str, Any]]) -> str:
    return "".join(str(r.get("plain_text") or r.get("text", {}).get("content") or "") for r in rich or [])


_PAGE_ID = re.compile(r"([0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12})(?:[?#].*)?$")


def page_id(ref: str) -> str:
    """Take the page ID out of a page's address, or give an ID back without its dashes.

    Args:
        ref: A page address (`https://…/Title-<32 hex>?…`), an ID with or without dashes, or any other text.

    Returns:
        The 32-character ID; the text itself when it holds none (so a name that is not an address passes through).

    Example:
        >>> page_id("https://www.notion.so/me/FastAPI-124791d2c4e380b086defba8b13fd766?pvs=4")
        '124791d2c4e380b086defba8b13fd766'
        >>> page_id("124791d2-c4e3-80b0-86de-fba8b13fd766"), page_id("p1")
        ('124791d2c4e380b086defba8b13fd766', 'p1')
    """
    m = _PAGE_ID.search(ref.strip())
    return m.group(1).replace("-", "") if m else ref


def _title(page: dict[str, Any]) -> str:
    for prop in (page.get("properties") or {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _plain(prop.get("title") or []).strip()  # Notion titles often end in a space; "FastAPI " is "FastAPI"
    return ""


def _rich(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text[i : i + 2000]}} for i in range(0, max(len(text), 1), 2000)] if text else []


def markdown_to_blocks(md: str) -> list[dict[str, Any]]:
    r"""Turn Markdown into Notion blocks: headings (1–3), bullets, quotes, code fences and paragraphs.

    Args:
        md: Markdown text.

    Returns:
        Notion block objects, one per non-empty line (one per code fence).

    Example:
        >>> [b["type"] for b in markdown_to_blocks("# 제목\n- 하나\n> 인용\n본문")]
        ['heading_1', 'bulleted_list_item', 'quote', 'paragraph']
    """
    blocks: list[dict[str, Any]] = []
    fence: list[str] | None = None
    for line in md.split("\n"):
        if line.strip().startswith("```"):
            if fence is None:
                fence = []
            else:
                blocks.append({"object": "block", "type": "code", "code": {"rich_text": _rich("\n".join(fence)), "language": "plain text"}})
                fence = None
            continue
        if fence is not None:
            fence.append(line)
            continue
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            kind = f"heading_{len(m.group(1))}"
            blocks.append({"object": "block", "type": kind, kind: {"rich_text": _rich(m.group(2))}})
        elif re.match(r"^[-*]\s+", s):
            blocks.append(
                {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rich(re.sub(r"^[-*]\s+", "", s))}}
            )
        elif s.startswith(">"):
            blocks.append({"object": "block", "type": "quote", "quote": {"rich_text": _rich(s.lstrip("> "))}})
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich(s)}})
    return blocks


def block_text(block: dict[str, Any]) -> str:
    """Turn one Notion block back into a Markdown line.

    Args:
        block: A Notion block object.

    Returns:
        The block's text with its Markdown mark (heading, bullet, quote, code fence). A link block gives its address and a
        table row its cells; blocks that hold no text give an empty string.

    Example:
        >>> block_text(markdown_to_blocks("## 소제목")[0])
        '## 소제목'
        >>> block_text({"type": "bookmark", "bookmark": {"url": "https://a.b"}})
        '[북마크] https://a.b'
        >>> block_text({"type": "table_row", "table_row": {"cells": [[{"plain_text": "a"}], [{"plain_text": "b"}]]}})
        '| a | b |'
    """
    kind = block.get("type", "")
    body = block.get(kind) or {}
    text = _plain(body.get("rich_text") or [])
    if kind.startswith("heading_"):
        return "#" * int(kind[-1]) + " " + text
    if kind in ("bulleted_list_item", "to_do", "toggle"):
        return "- " + text
    if kind in ("bookmark", "embed", "link_preview"):
        return msg("[Bookmark] {url}", url=body.get("url", ""))
    if kind == "table_row":
        return "| " + " | ".join(_plain(cell) for cell in body.get("cells") or []) + " |"
    if kind == "numbered_list_item":
        return "1. " + text
    if kind == "quote":
        return "> " + text
    if kind == "code":
        return "```\n" + text + "\n```"
    return text


def _retry_wait(error: urllib.error.HTTPError) -> float:
    """Seconds to wait after a 429: the Retry-After header, at most 10, one second when it is missing or unreadable."""
    try:
        return min(max(float(error.headers.get("Retry-After", 1)), 0.0), 10.0)
    except (TypeError, ValueError):
        return 1.0


def _property_value(prop: dict[str, Any]) -> str:
    kind = prop.get("type", "")
    value = prop.get(kind)
    if kind == "rich_text":
        return _plain(value or [])
    if kind in ("select", "status"):
        return str((value or {}).get("name") or "")
    if kind == "multi_select":
        return ", ".join(str(v.get("name") or "") for v in value or [])
    if kind == "date":
        start, end = (value or {}).get("start") or "", (value or {}).get("end")
        return f"{start} → {end}" if end else start
    if kind == "number":
        return "" if value is None else str(value)
    if kind == "checkbox":
        return "✔" if value else ""
    if kind in ("url", "email", "phone_number"):
        return str(value or "")
    return ""


def properties_text(page: dict[str, Any]) -> str:
    r"""Write the filled properties of a page (a database row's columns) as a block of lines.

    The title is left out (it is the page's name) and so are empty values and kinds with no plain value (formulas, relations, files).

    Args:
        page: A Notion page object.

    Returns:
        `---`, one `name: value` line per filled property, `---` and a newline; empty when no property has a value.

    Example:
        >>> page = {"properties": {"분류": {"type": "select", "select": {"name": "개발"}}, "빈칸": {"type": "select", "select": None}}}
        >>> print(properties_text(page), end="")
        ---
        분류: 개발
        ---
        >>> properties_text({"properties": {}})
        ''
    """
    lines = []
    for name, prop in (page.get("properties") or {}).items():
        value = _property_value(prop) if isinstance(prop, dict) else ""
        if value:
            lines.append(f"{name}: {value}")
    return "---\n" + "\n".join(lines) + "\n---\n" if lines else ""


class NotionAdapter(Adapter):
    """A knowledge store in Notion, reached with an integration token.

    Attributes:
        parent: The page new notes are created under (ID without dashes).
        token: The integration token.

    Example:
        >>> NotionAdapter("abc-123", token=None)
        Traceback (most recent call last):
        ...
        lanternspec.learn.knowledge.KnowledgeError: Notion 토큰이 없습니다 — 환경 변수 NOTION_TOKEN (또는 knowledge.token_env)
    """

    name = "notion"

    def __init__(self, parent_id: str, token: str | None, opener: Callable[..., Any] | None = None) -> None:
        """Set up the adapter.

        Args:
            parent_id: The page new notes are created under.
            token: The integration token.
            opener: Replaces urllib.request.urlopen (tests pass a fake).

        Raises:
            KnowledgeError: There is no token.
        """
        if not token:
            raise KnowledgeError(msg("No Notion token — environment variable NOTION_TOKEN (or knowledge.token_env)"))
        self.parent = parent_id.replace("-", "")
        self.token = token
        self._open = opener or urllib.request.urlopen

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        req = urllib.request.Request(
            API + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.token}", "Notion-Version": VERSION, "Content-Type": "application/json"},
        )
        tries = 0
        while True:
            try:
                with self._open(req) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429 and tries < RETRIES:  # rate limited: wait as long as Notion says, then ask again
                    tries += 1
                    time.sleep(_retry_wait(e))
                    continue
                raise KnowledgeError(
                    msg("Notion API error {code}: {value}", code=e.code, value=e.read().decode("utf-8", "replace")[:200])
                ) from e
            except urllib.error.URLError as e:  # pragma: no cover
                raise KnowledgeError(msg("Couldn't connect to Notion: {reason}", reason=e.reason)) from e

    def search(self, query: str, aliases: list[str] | None = None, limit: int = 5) -> list[Hit]:
        """Implement Adapter.search with Notion's page search, once per name.

        Args:
            query: The term.
            aliases: Other names for the term.
            limit: Most results to return.

        Returns:
            The best matches; the path is the page's address (read takes it back) and the summary is empty.

        Raises:
            KnowledgeError: The API call failed.

        Example:
            >>> NotionAdapter(parent, token).search("JWT")[0].title  # doctest: +SKIP
            'JWT'
        """
        seen: dict[str, Hit] = {}
        terms: list[str] = [query, *(aliases or [])]
        for i, term in enumerate(terms):
            res = self._call("POST", "/search", {"query": term, "page_size": limit, "filter": {"property": "object", "value": "page"}})
            for page in res.get("results") or []:
                pid = page.get("id", "")
                title = _title(page)
                score = (100 if title.lower() == term.lower() else 40) - i
                if pid not in seen or seen[pid].score < score:
                    # the path is where a person can open the page (a debt card keeps it as its note); read takes the ID out of it
                    seen[pid] = Hit(
                        title=title,
                        path=page.get("url") or pid,
                        summary="",
                        updated=str(page.get("last_edited_time", ""))[:10],
                        score=score,
                    )
        return sorted(seen.values(), key=lambda h: -h.score)[:limit]

    def read(self, path: str) -> str:
        r"""Implement Adapter.read by reading a page's blocks as Markdown lines.

        Blocks inside blocks (under a heading, a toggle, a list item) are read too, each level indented two spaces, down to
        `MAX_DEPTH` levels and `MAX_REQUESTS` requests. A subpage or database inside the page is named with its ID, not read.
        A database row starts with its filled properties.

        Args:
            path: The page's address (what a search gave) or its ID.

        Returns:
            The page's text.

        Raises:
            KnowledgeError: Reading the blocks failed (the properties are left out when only they fail).

        Example:
            >>> NotionAdapter(parent, token).read(page_id)  # doctest: +SKIP
            '---\n분류: 개발\n---\n# JWT\n  서명된 토큰'
        """
        path = page_id(path)
        lines = self._read_blocks(path, 0, [MAX_REQUESTS])
        try:
            header = properties_text(self._call("GET", f"/pages/{path}"))
        except KnowledgeError:  # not a page, or the properties cannot be read: the body is still worth returning
            header = ""
        return header + "\n".join(lines)

    def _read_blocks(self, block_id: str, depth: int, budget: list[int]) -> list[str]:
        """Read the children of a block as lines, going down into the ones that have children."""
        lines: list[str] = []
        cursor = None
        while True:
            if budget[0] <= 0:
                if budget[0] < 0:  # already said so once
                    return lines
                budget[0] = -1
                return [*lines, "  " * depth + msg("… (only part was read: too many requests)")]
            budget[0] -= 1
            q = f"/blocks/{block_id}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            res = self._call("GET", q)
            for block in res.get("results") or []:
                lines += self._block_lines(block, depth, budget)
            if not res.get("has_more"):
                return lines
            cursor = res.get("next_cursor")

    def _block_lines(self, block: dict[str, Any], depth: int, budget: list[int]) -> list[str]:
        """The lines of one block (indented by its depth) and of everything inside it."""
        kind = block.get("type", "")
        pad = "  " * depth
        if kind in _OTHER_DOCUMENT:
            title = (block.get(kind) or {}).get("title", "")
            return [pad + "- " + msg(_OTHER_DOCUMENT[kind], title=title, id=block.get("id", ""))]
        text = block_text(block)
        has_children = bool(block.get("has_children"))
        skip = kind in _NO_LINE or (has_children and not text)
        lines = [] if skip else [pad + line if line else "" for line in text.split("\n")]
        if has_children and depth < MAX_DEPTH:
            lines += self._read_blocks(block.get("id", ""), depth + 1, budget)
        return lines

    def write(self, rel_path: str, content: str) -> str:
        r"""Implement Adapter.write by creating a page under the parent page.

        Args:
            rel_path: The note's name (its last path part, without `.md`, becomes the title).
            content: The note's Markdown.

        Returns:
            The new page's URL (or ID).

        Raises:
            KnowledgeError: The API call failed.

        Example:
            >>> NotionAdapter(parent, token).write("JWT.md", "# JWT\n")  # doctest: +SKIP
            'https://www.notion.so/JWT-…'
        """
        title = re.sub(r"\.md$", "", rel_path.rsplit("/", 1)[-1])
        blocks = markdown_to_blocks(content)
        page = self._call(
            "POST",
            "/pages",
            {"parent": {"page_id": self.parent}, "properties": {"title": {"title": _rich(title)}}, "children": blocks[:100]},
        )
        for i in range(100, len(blocks), 100):  # Notion takes 100 blocks per request
            self._call("PATCH", f"/blocks/{page['id']}/children", {"children": blocks[i : i + 100]})
        return str(page.get("url") or page.get("id"))


def from_config(k: dict[str, Any]) -> NotionAdapter:
    """Create the adapter from the `knowledge` block of lantern.yaml.

    Args:
        k: The knowledge settings (path = parent page ID, token_env = token variable).

    Returns:
        The adapter.

    Raises:
        KnowledgeError: The token variable is not set.

    Example:
        >>> from_config({"path": "abc", "token_env": "NO_SUCH_TOKEN_VAR"})
        Traceback (most recent call last):
        ...
        lanternspec.learn.knowledge.KnowledgeError: Notion 토큰이 없습니다 — 환경 변수 NOTION_TOKEN (또는 knowledge.token_env)
    """
    return NotionAdapter(str(k.get("path") or ""), os.environ.get(str(k.get("token_env") or "NOTION_TOKEN")))
