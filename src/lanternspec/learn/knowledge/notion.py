"""Notion adapter — the same four questions over the Notion REST API (stdlib only).

lantern.yaml:
    knowledge:
      type: notion
      path: <parent page id>      # where approved notes are created
      token_env: NOTION_TOKEN     # (optional) env var holding the integration token

The integration only sees pages shared with it; we never edit existing pages (P6).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from . import Adapter, Hit, KnowledgeError

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


def _plain(rich: list[dict[str, Any]]) -> str:
    return "".join(str(r.get("plain_text") or r.get("text", {}).get("content") or "") for r in rich or [])


def _title(page: dict[str, Any]) -> str:
    for prop in (page.get("properties") or {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _plain(prop.get("title") or [])
    return ""


def _rich(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text[i : i + 2000]}} for i in range(0, max(len(text), 1), 2000)] if text else []


def markdown_to_blocks(md: str) -> list[dict[str, Any]]:
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
    kind = block.get("type", "")
    body = block.get(kind) or {}
    text = _plain(body.get("rich_text") or [])
    if kind.startswith("heading_"):
        return "#" * int(kind[-1]) + " " + text
    if kind in ("bulleted_list_item", "to_do"):
        return "- " + text
    if kind == "numbered_list_item":
        return "1. " + text
    if kind == "quote":
        return "> " + text
    if kind == "code":
        return "```\n" + text + "\n```"
    return text


class NotionAdapter(Adapter):
    name = "notion"

    def __init__(self, parent_id: str, token: str | None, opener: Callable[..., Any] | None = None) -> None:
        if not token:
            raise KnowledgeError("Notion 토큰이 없습니다 — 환경 변수 NOTION_TOKEN (또는 knowledge.token_env)")
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
        try:
            with self._open(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:  # pragma: no cover - needs the network
            raise KnowledgeError(f"Notion API 오류 {e.code}: {e.read().decode('utf-8', 'replace')[:200]}") from e
        except urllib.error.URLError as e:  # pragma: no cover
            raise KnowledgeError(f"Notion에 연결하지 못했습니다: {e.reason}") from e

    def search(self, query: str, aliases: list[str] | None = None, limit: int = 5) -> list[Hit]:
        seen: dict[str, Hit] = {}
        terms: list[str] = [query, *(aliases or [])]
        for i, term in enumerate(terms):
            res = self._call("POST", "/search", {"query": term, "page_size": limit, "filter": {"property": "object", "value": "page"}})
            for page in res.get("results") or []:
                pid = page.get("id", "")
                title = _title(page)
                score = (100 if title.lower() == term.lower() else 40) - i
                if pid not in seen or seen[pid].score < score:
                    seen[pid] = Hit(
                        title=title, path=pid, summary=page.get("url", ""), updated=str(page.get("last_edited_time", ""))[:10], score=score
                    )
        return sorted(seen.values(), key=lambda h: -h.score)[:limit]

    def read(self, path: str) -> str:
        lines, cursor = [], None
        while True:
            q = f"/blocks/{path}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            res = self._call("GET", q)
            lines += [block_text(b) for b in res.get("results") or []]
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        return "\n".join(lines)

    def write(self, rel_path: str, content: str) -> str:
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
    return NotionAdapter(str(k.get("path") or ""), os.environ.get(str(k.get("token_env") or "NOTION_TOKEN")))
