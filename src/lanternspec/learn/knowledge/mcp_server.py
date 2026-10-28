"""`lantern mcp` — the knowledge contract (search · read · propose · write) as an MCP server over stdio.

Skills call the same functions through `lantern knowledge …`. This server is for tools that
prefer MCP; register it with `lantern install --mcp`.
Newline-delimited JSON-RPC 2.0, no dependencies.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from ... import __version__
from ...core.project import Project
from . import KnowledgeError, adapter_for, drafts

PROTOCOL = "2025-06-18"

TOOLS = [
    {
        "name": "search",
        "description": "이 용어에 관한 노트가 있나? → 제목 · 위치 · 요약 · 수정일 목록",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "aliases": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read",
        "description": "이 노트 내용은? → 본문",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "propose",
        "description": "이 주제로 노트를 만들어도 되나? → 초안 (승인 대기, 우리 쪽 📒 부채/노트 초안/)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "area": {"type": "string"},
                "target": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "write",
        "description": "(사람이 승인한 뒤에만) 초안을 지식 저장소에 쓴다 → 만들어진 위치. propose_only 저장소는 거절",
        "inputSchema": {"type": "object", "properties": {"draft": {"type": "string"}, "target": {"type": "string"}}, "required": ["draft"]},
    },
]


def call(project: Project, name: str, args: dict[str, Any]) -> Any:
    """Run one knowledge tool.

    Args:
        project: The project.
        name: "search", "read", "propose" or "write".
        args: The tool's arguments, as in TOOLS.

    Returns:
        The tool's result, ready for JSON.

    Raises:
        KnowledgeError: The tool is unknown or the store refused.
        KeyError: A required argument is missing.

    Example:
        >>> call(project, "search", {"query": "JWT"})[0]["title"]  # doctest: +SKIP
        'JWT'
    """
    if name == "search":
        hits = adapter_for(project).search(str(args["query"]), aliases=list(args.get("aliases") or []), limit=int(args.get("limit") or 5))
        return [h.to_dict() for h in hits]
    if name == "read":
        return {"path": args["path"], "content": adapter_for(project).read(str(args["path"]))}
    if name == "propose":
        return drafts.propose(
            project, str(args["title"]), args.get("content"), area=str(args.get("area") or ""), target=str(args.get("target") or "")
        )
    if name == "write":
        draft = project.root / str(args["draft"])
        if not draft.exists():
            draft = project.docs / str(args["draft"])
        return drafts.write_draft(project, draft, args.get("target"))
    raise KnowledgeError(f"알 수 없는 도구: {name}")


def handle(project: Project, msg: dict[str, Any]) -> dict[str, Any] | None:
    """Answer one JSON-RPC message.

    Args:
        project: The project.
        msg: The parsed message.

    Returns:
        The response; None for notifications. Tool failures come back as results with isError.

    Example:
        >>> handle(None, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        {'jsonrpc': '2.0', 'id': 1, 'result': {}}
    """
    method = msg.get("method")
    mid = msg.get("id")
    if mid is None:  # notification
        return None
    try:
        if method == "initialize":
            result: Any = {
                "protocolVersion": msg.get("params", {}).get("protocolVersion") or PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "lantern-knowledge", "version": __version__},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = msg.get("params") or {}
            try:
                data = call(project, str(params.get("name")), params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}
            except (KnowledgeError, KeyError, FileExistsError, FileNotFoundError, ValueError) as e:
                result = {"content": [{"type": "text", "text": str(e)}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    except Exception as e:  # pragma: no cover - last resort
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(project: Project) -> int:
    """Serve MCP over stdin and stdout until stdin closes.

    Args:
        project: The project.

    Returns:
        The exit code (0).

    Example:
        >>> serve(project)  # doctest: +SKIP
        0
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            out = handle(project, msg)
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0
