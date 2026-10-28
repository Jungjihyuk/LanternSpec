"""`.lantern/installed.json` — what the installer wrote, so upgrades only touch its own files.

Responsibilities:
    - create the `.lantern` state folder and its .gitignore
    - read and write installed.json (installed version, tools, file hashes, template hashes)
    - hash text and files to tell whether someone edited an installed copy

Not here:
    - deciding what to install or refresh → tools/install.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .messages import msg
from .project import Project

INSTALLED = "installed.json"

STATE_GITIGNORE = """# {note}
runs.jsonl
runs-state/
hook-state/
pack/
"""


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest of a text (UTF-8).

    Args:
        text: Any text.

    Returns:
        64 hex characters.

    Example:
        >>> sha256_text("lantern")[:12]
        'c5220b3c4266'
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a text file's contents.

    Args:
        path: A UTF-8 text file.

    Returns:
        64 hex characters, the same as sha256_text of the file's text.

    Raises:
        OSError: The file cannot be read.

    Example:
        >>> sha256_file(Path("AGENTS.md"))  # doctest: +SKIP
        '3b1f…'
    """
    return sha256_text(path.read_text(encoding="utf-8"))


def ensure_state_dir(project: Project) -> Path:
    """Create the `.lantern` folder (with a .gitignore for personal records) when missing.

    Args:
        project: The project.

    Returns:
        The state folder.

    Example:
        >>> ensure_state_dir(project).name  # doctest: +SKIP
        '.lantern'
    """
    project.state.mkdir(parents=True, exist_ok=True)
    gi = project.state / ".gitignore"
    if not gi.exists():
        gi.write_text(STATE_GITIGNORE.format(note=msg("LanternSpec local state — personal records are not committed")), encoding="utf-8")
    return project.state


def load(project: Project) -> dict[str, Any]:
    """Read installed.json.

    Args:
        project: The project.

    Returns:
        The record with at least the keys version, tools, files and templates;
        an empty record when nothing was installed yet.

    Example:
        >>> load(project)["tools"]  # doctest: +SKIP
        ['claude']
    """
    p = project.state / INSTALLED
    if not p.exists():
        return {"version": None, "tools": [], "files": {}, "templates": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("files", {})
    data.setdefault("templates", {})
    data.setdefault("tools", [])
    return data


def save(project: Project, data: dict[str, Any]) -> None:
    """Write installed.json (sorted keys, so diffs stay small).

    Args:
        project: The project.
        data: The whole record, as returned by load and then changed.

    Example:
        >>> save(project, load(project))  # doctest: +SKIP
    """
    ensure_state_dir(project)
    (project.state / INSTALLED).write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
