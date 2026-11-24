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
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ...core.messages import msg
from . import Adapter, Hit, KnowledgeError, keychain

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
MAX_DEPTH = 6  # how many levels of blocks inside blocks one read goes down
MAX_REQUESTS = 100  # most block requests one read makes (Notion answers about three a second)
RETRIES = 3  # how many times a rate-limited (429) request is tried again
CACHE_SECONDS = 600  # how long a kept list of the pages is used before the pages are asked for again
FRESH_SECONDS = 30  # a list fetched this recently is not fetched again just because a search found nothing
CACHE_FILE = "knowledge-notion.json"  # in the project's state folder (a personal record: it is never committed)
MAX_LIST_REQUESTS = 100  # a stop for listing the pages (100 pages each): a workspace of 10,000 pages
_NO_LINE = ("table_of_contents", "breadcrumb")  # blocks that hold no text of their own
_OTHER_DOCUMENT = {"child_page": "[Subpage] {title} ({id})", "child_database": "[Database] {title} ({id})"}  # named, not followed


def _plain(rich: list[dict[str, Any]]) -> str:
    return "".join(str(r.get("plain_text") or r.get("text", {}).get("content") or "") for r in rich or [])


_PAGE_ID = re.compile(r"([0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12})(?:[?#].*)?$")


class NotionError(KnowledgeError):
    """A call to Notion failed.

    Attributes:
        status: The HTTP status code Notion answered with; 0 when it could not be reached.

    Example:
        >>> NotionError("Notion API 오류 401", 401).status
        401
    """

    def __init__(self, message: str, status: int = 0) -> None:
        """Keep the message and the HTTP status.

        Args:
            message: What went wrong, for a person.
            status: The HTTP status code; 0 when Notion could not be reached.
        """
        super().__init__(message)
        self.status = status


def token_sources(
    env_name: str = "NOTION_TOKEN", store: Any = keychain, env: Mapping[str, str] | None = None
) -> tuple[str | None, str | None]:
    """Give the token of the environment variable and the token of the Keychain apart, each None when there is none.

    Args:
        env_name: The name of the environment variable, which is also the Keychain service name.
        store: Where the Keychain is read (the keychain module; tests pass a fake).
        env: The environment; the process's own when None.

    Returns:
        The variable's token and the Keychain's token. `notion_token` uses the Keychain's when it has one, so when both
        exist and differ the variable is ignored.

    Example:
        >>> token_sources("X", env={"X": "abc"}, store=type("K", (), {"read": staticmethod(lambda s: None)}))
        ('abc', None)
    """
    value = (os.environ if env is None else env).get(env_name, "").strip()
    return value or None, store.read(env_name)


def notion_token(env_name: str = "NOTION_TOKEN", store: Any = keychain, env: Mapping[str, str] | None = None) -> str | None:
    """Find the integration token: the Keychain item first (on a Mac), then the environment variable of the same name.

    The Keychain comes first because it is what `lantern knowledge setup notion` keeps up to date. A variable left in a shell
    file from an earlier setup holds the value of when the terminal was opened and would otherwise hide a newer token.

    Args:
        env_name: The name of the environment variable, which is also the Keychain service name (`knowledge.token_env`).
        store: Where the Keychain is read (the keychain module; tests pass a fake).
        env: The environment; the process's own when None.

    Returns:
        The token; None when there is none.

    Example:
        >>> notion_token("X", env={"X": "abc"})
        'abc'
    """
    stored = store.read(env_name)
    if stored:
        return stored
    return (os.environ if env is None else env).get(env_name, "").strip() or None


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


def _property_items(prop: dict[str, Any]) -> list[str]:
    """The values of one property as separate texts (a multi-select gives one per choice); empty when it has none or no plain value."""
    kind = prop.get("type", "")
    value = prop.get(kind)
    if kind == "rich_text":
        items = [_plain(value or [])]
    elif kind in ("select", "status"):
        items = [str((value or {}).get("name") or "")]
    elif kind == "multi_select":
        items = [str(v.get("name") or "") for v in value or []]
    elif kind == "date":
        start, end = (value or {}).get("start") or "", (value or {}).get("end")
        items = [f"{start} → {end}" if end else start]
    elif kind == "number":
        items = ["" if value is None else str(value)]
    elif kind == "checkbox":
        items = ["✔" if value else ""]
    elif kind in ("url", "email", "phone_number"):
        items = [str(value or "")]
    else:
        items = []
    return [i for i in items if i]


def _property_value(prop: dict[str, Any]) -> str:
    return ", ".join(_property_items(prop))


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


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().strip()


def listed(page: dict[str, Any]) -> dict[str, Any]:
    """Keep what a search needs of a page the search API listed: its title, address, edit date and the values of its properties.

    Args:
        page: A Notion page object, as the search lists it.

    Returns:
        `id`, `title`, `url` (the ID when Notion gave none), `edited` (a date) and `props` (name → values; no title, no empty ones).

    Example:
        >>> page = {"id": "p", "url": "u", "last_edited_time": "2026-11-20T01:00:00Z", "properties": {
        ...     "이름": {"type": "title", "title": [{"plain_text": "모니터링 "}]},
        ...     "유형": {"type": "multi_select", "multi_select": [{"name": "Grafana"}]}}}
        >>> listed(page)["props"], listed(page)["title"]
        ({'유형': ['Grafana']}, '모니터링')
    """
    props = {
        name: items
        for name, prop in (page.get("properties") or {}).items()
        if isinstance(prop, dict) and prop.get("type") != "title" and (items := _property_items(prop))
    }
    return {
        "id": page.get("id", ""),
        "title": _title(page),
        "url": page.get("url") or page.get("id", ""),
        "edited": str(page.get("last_edited_time", ""))[:10],
        "props": props,
    }


def match(pages: list[dict[str, Any]], terms: list[str], limit: int) -> list[Hit]:
    """Find the pages that a name (or one of its aliases) belongs to, by title and by property values.

    A title equal to the name scores 100 and one containing it 60; a property value equal to it 50 and one containing it 30.
    An alias scores one less for each place it stands after the first name. The result says which property matched.
    What the pages' text says is not looked at.

    Args:
        pages: What `listed` made of each page.
        terms: The name and its aliases.
        limit: Most results to return.

    Returns:
        The best matches, best first (the more recently edited first among equals); the summary is `property: value` for a
        match in a property and empty for one in the title.

    Example:
        >>> pages = [{"title": "JWT", "url": "u1", "edited": "2026-01-01", "props": {}},
        ...          {"title": "인증", "url": "u2", "edited": "2026-01-02", "props": {"유형": ["JWT 토큰"]}}]
        >>> [(h.title, h.score, h.summary) for h in match(pages, ["JWT"], 5)]
        [('JWT', 100, ''), ('인증', 30, '유형: JWT 토큰')]
    """
    names = [_fold(t) for t in terms if t and t.strip()]
    hits: list[Hit] = []
    for page in pages:
        title = _fold(page["title"])
        best, why = 0, ""
        for i, name in enumerate(names):
            score, note = 0, ""
            if title == name:
                score = 100
            elif title and name in title:
                score = 60
            else:
                for prop, items in (page.get("props") or {}).items():
                    for item in items:
                        s = 50 if _fold(item) == name else 30 if name in _fold(item) else 0
                        if s > score:
                            score, note = s, f"{prop}: {item}"
            if score and score - i > best:
                best, why = score - i, note
        if best:
            hits.append(Hit(title=page["title"], path=page["url"], summary=why, updated=page["edited"], score=best))
    hits.sort(key=lambda h: h.updated, reverse=True)
    hits.sort(key=lambda h: -h.score)  # stable: the more recently edited stays first among equals
    return hits[:limit]


class NotionAdapter(Adapter):
    """A knowledge store in Notion, reached with an integration token.

    Attributes:
        parent: The page new notes are created under (ID without dashes).
        token: The integration token.

    Example:
        >>> NotionAdapter("abc-123", token=None)
        Traceback (most recent call last):
        ...
        lanternspec.learn.knowledge.KnowledgeError: Notion 토큰이 없습니다 — `lantern knowledge setup notion`을 실행하세요
    """

    name = "notion"

    def __init__(self, parent_id: str, token: str | None, opener: Callable[..., Any] | None = None, state_dir: Path | None = None) -> None:
        """Set up the adapter.

        Args:
            parent_id: The page new notes are created under.
            token: The integration token.
            opener: Replaces urllib.request.urlopen (tests pass a fake).
            state_dir: Where the list of the pages is kept between runs; None keeps it only for this run.

        Raises:
            KnowledgeError: There is no token.
        """
        if not token:
            raise KnowledgeError(msg("No Notion token — run `lantern knowledge setup notion`"))
        self.parent = parent_id.replace("-", "")
        self.token = token
        self._open = opener or urllib.request.urlopen
        self.state_dir = state_dir
        self._memo: tuple[float, list[dict[str, Any]]] | None = None  # when the list was fetched, and the list

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
                raise NotionError(
                    msg("Notion API error {code}: {value}", code=e.code, value=e.read().decode("utf-8", "replace")[:200]), e.code
                ) from e
            except urllib.error.URLError as e:  # pragma: no cover
                raise NotionError(msg("Couldn't connect to Notion: {reason}", reason=e.reason)) from e

    def search(self, query: str, aliases: list[str] | None = None, limit: int = 5) -> list[Hit]:
        """Implement Adapter.search over the titles and property values of all the pages, from a list fetched whole.

        Notion's own search looks at titles only, so the pages (with their properties) are listed once and searched here.
        The list is kept for `CACHE_SECONDS`. A search that finds nothing in a list older than `FRESH_SECONDS` fetches the list
        once more and looks again, so a note added a minute ago is not missed.

        Args:
            query: The term.
            aliases: Other names for the term.
            limit: Most results to return.

        Returns:
            The best matches; the path is the page's address (read takes it back) and the summary says which property matched.

        Raises:
            KnowledgeError: The API call failed.

        Example:
            >>> NotionAdapter(parent, token).search("JWT")[0].title  # doctest: +SKIP
            'JWT'
        """
        terms = [query, *(aliases or [])]
        pages, fresh = self._list()
        hits = match(pages, terms, limit)
        if not hits and not fresh:
            pages, _ = self._list(force=True)
            hits = match(pages, terms, limit)
        return hits

    def overview(self, newest: int = 5) -> tuple[int, list[str]]:
        """Count the pages the integration can see and name the ones edited most recently (the list is fetched anew).

        Args:
            newest: How many titles to give.

        Returns:
            The number of pages and the titles of the `newest` most recently edited ones.

        Raises:
            KnowledgeError: The API call failed (a token Notion doesn't accept is the usual reason).

        Example:
            >>> NotionAdapter(parent, token).overview()  # doctest: +SKIP
            (445, ['모니터링', 'FastAPI'])
        """
        pages, _ = self._list(force=True)
        recent = sorted(pages, key=lambda p: p["edited"], reverse=True)[:newest]
        return len(pages), [p["title"] or msg("(untitled)") for p in recent]

    def can_see(self, ref: str) -> bool:
        """Tell whether the integration can open a page (it is shared with it).

        Args:
            ref: The page's address or ID.

        Returns:
            True when Notion gives the page; False when it doesn't (not shared, or no such page).

        Example:
            >>> NotionAdapter(parent, token).can_see(page_id)  # doctest: +SKIP
            True
        """
        try:
            self._call("GET", f"/pages/{page_id(ref)}")
        except KnowledgeError:
            return False
        return True

    def _list(self, force: bool = False) -> tuple[list[dict[str, Any]], bool]:
        """The listed pages and whether they were fetched just now (within `FRESH_SECONDS`)."""
        now = time.time()
        if not force:
            got = self._memo or self._read_kept()
            if got and 0 <= now - got[0] < CACHE_SECONDS:
                self._memo = got
                return got[1], now - got[0] < FRESH_SECONDS
        pages = [listed(p) for p in self._fetch_pages()]
        self._memo = (now, pages)
        self._write_kept(now, pages)
        return pages, True

    def _fetch_pages(self) -> list[dict[str, Any]]:
        """Ask for every page the integration can see, 100 at a time."""
        out: list[dict[str, Any]] = []
        cursor = None
        for _ in range(MAX_LIST_REQUESTS):
            body: dict[str, Any] = {"page_size": 100, "filter": {"property": "object", "value": "page"}}
            if cursor:
                body["start_cursor"] = cursor
            res = self._call("POST", "/search", body)
            out += res.get("results") or []
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        return out

    def _read_kept(self) -> tuple[float, list[dict[str, Any]]] | None:
        """The list kept in the state folder; None when there is none or it can't be used."""
        if self.state_dir is None:
            return None
        try:
            data = json.loads((self.state_dir / CACHE_FILE).read_text(encoding="utf-8"))
            return float(data["fetched_at"]), [p for p in data["pages"] if isinstance(p, dict) and "title" in p and "url" in p]
        except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError):
            return None

    def _write_kept(self, fetched_at: float, pages: list[dict[str, Any]]) -> None:
        """Keep the list for the next run; a folder that can't be written to just means no list is kept."""
        if self.state_dir is None:
            return
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            (self.state_dir / CACHE_FILE).write_text(
                json.dumps({"fetched_at": fetched_at, "pages": pages}, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass

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


def from_config(k: dict[str, Any], state_dir: Path | None = None) -> NotionAdapter:
    """Create the adapter from the `knowledge` block of lantern.yaml.

    Args:
        k: The knowledge settings (path = parent page ID, token_env = token variable).
        state_dir: Where the list of the pages is kept between runs (the project's state folder).

    Returns:
        The adapter.

    Raises:
        KnowledgeError: The token variable is not set.

    Example:
        >>> from_config({"path": "abc", "token_env": "NO_SUCH_TOKEN_VAR"})
        Traceback (most recent call last):
        ...
        lanternspec.learn.knowledge.KnowledgeError: Notion 토큰이 없습니다 — `lantern knowledge setup notion`을 실행하세요
    """
    return NotionAdapter(str(k.get("path") or ""), notion_token(str(k.get("token_env") or "NOTION_TOKEN")), state_dir=state_dir)
