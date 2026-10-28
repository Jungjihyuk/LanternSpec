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
from ...core.messages import msg
from ...core.project import Project
from . import KnowledgeError, adapter_for, drafts

PROTOCOL = "2025-06-18"

TOOLS = [  # descriptions in English; msg() translates them
    {
        "name": "search",
        "description": "Is there a note on this term? → a list of titles · places · summaries · modified dates",
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
        "description": "What does this note say? → its body",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "propose",
        "description": "May a note on this topic be made? → a draft (awaiting approval, in our debt note-drafts folder)",
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
        "description": (
            "(Only after a person approves) write the draft to the knowledge store → where it was made. A propose_only store refuses"
        ),
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
    raise KnowledgeError(msg("Unknown tool: {name}", name=name))


def handle(project: Project, request: dict[str, Any]) -> dict[str, Any] | None:
    """Answer one JSON-RPC message.

    Args:
        project: The project.
        request: The parsed message.

    Returns:
        The response; None for notifications. Tool failures come back as results with isError.

    Example:
        >>> handle(None, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        {'jsonrpc': '2.0', 'id': 1, 'result': {}}
    """
    method = request.get("method")
    mid = request.get("id")
    if mid is None:  # notification
        return None
    try:
        if method == "initialize":
            result: Any = {
                "protocolVersion": request.get("params", {}).get("protocolVersion") or PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "lantern-knowledge", "version": __version__},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [{**t, "description": msg(t["description"])} for t in TOOLS]}
        elif method == "tools/call":
            params = request.get("params") or {}
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
            request = json.loads(line)
        except json.JSONDecodeError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            out = handle(project, request)
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0
