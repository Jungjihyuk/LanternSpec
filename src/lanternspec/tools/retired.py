"""Take out of the AI tools' settings what earlier versions of LanternSpec put there and no version uses any more.

Responsibilities:
    - the `lantern-knowledge` server that `install --mcp` registered (up to 0.4.0): the command behind it is gone, so a tool
      that still starts it would report an error

Not here:
    - what is installed now → tools/install.py and each tool's file

Only an entry that is exactly what was written is taken out; one a person changed stays, and is named.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..core.messages import msg
from ..core.project import Project, read, write

NAME = "lantern-knowledge"
ENTRY = {"command": "lantern", "args": ["mcp"]}
TOML = '[mcp_servers.lantern-knowledge]\ncommand = "lantern"\nargs = ["mcp"]\n'
PLUGIN = ".agents/plugins/lanternspec"
JSON_FILES = (".mcp.json", f"{PLUGIN}/mcp_config.json")
TOML_FILE = ".codex/config.toml"


def without_server(text: str) -> str | None:
    """Take the server out of the text of a JSON settings file.

    Args:
        text: The whole file.

    Returns:
        The new text, "" when nothing else is left; None when the entry isn't there, or isn't exactly what was written.

    Example:
        >>> without_server('{"mcpServers": {"lantern-knowledge": {"command": "lantern", "args": ["mcp"]}}}')
        ''
        >>> without_server('{"mcpServers": {"mine": {}}}') is None
        True
    """
    try:
        data = json.loads(text)
        servers = data["mcpServers"]
        if servers[NAME] != ENTRY:
            return None
    except (ValueError, KeyError, TypeError):
        return None
    del servers[NAME]
    if not servers:
        del data["mcpServers"]
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n" if data else ""


def without_server_toml(text: str) -> str | None:
    r"""Take the server out of the text of `.codex/config.toml`.

    Args:
        text: The whole file.

    Returns:
        The new text; None when the table isn't there, or isn't exactly what was written.

    Example:
        >>> without_server_toml('model = "x"\n\n[mcp_servers.lantern-knowledge]\ncommand = "lantern"\nargs = ["mcp"]\n')
        'model = "x"\n'
    """
    at = text.find(TOML)
    after = text[at + len(TOML) :].lstrip("\n")
    if at < 0 or (at and text[at - 1] != "\n") or not (after == "" or after.startswith("[")) or f"[mcp_servers.{NAME}." in text:
        return None
    before = text[:at].rstrip("\n")
    return "\n\n".join(part for part in (before, after.rstrip("\n")) if part) + ("\n" if before or after else "")


def _named(path: Path) -> bool:
    return path.exists() and re.search(rf'"{NAME}"|\[mcp_servers\.{NAME}\b', read(path)) is not None


def clean(project: Project) -> list[str]:
    """Take retired settings out of every AI tool's files, whichever tools are chosen now.

    Args:
        project: The project.

    Returns:
        What was taken out or left for the person, for the install report; empty when there is nothing.

    Example:
        >>> clean(project)  # doctest: +SKIP
        ['.mcp.json — lantern-knowledge를 뺐습니다 (더 이상 없는 명령)']
    """
    out: list[str] = []
    for rel in (*JSON_FILES, TOML_FILE):
        path = project.root / rel
        if not _named(path):
            continue
        new = without_server_toml(read(path)) if rel == TOML_FILE else without_server(read(path))
        if new is None:
            out.append(msg("{rel} — {name} is still there because it was edited: take it out, its command is gone", rel=rel, name=NAME))
            continue
        if new:
            write(path, new)
        else:
            path.unlink()
        out.append(msg("{rel} — {name} taken out (its command is gone)", rel=rel, name=NAME))
    plugin = project.root / PLUGIN
    if plugin.is_dir() and [p.name for p in plugin.iterdir()] == ["plugin.json"]:
        if read(plugin / "plugin.json") == json.dumps({"name": "lanternspec"}, indent=2) + "\n":  # it only carried the server
            (plugin / "plugin.json").unlink()
            plugin.rmdir()
            if not any(plugin.parent.iterdir()):
                plugin.parent.rmdir()
    return out
