"""`.lantern/installed.json` — what the installer wrote, so upgrades only touch its own files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .project import Project

INSTALLED = "installed.json"

STATE_GITIGNORE = """# LanternSpec 로컬 상태 — 개인 기록은 올리지 않는다
runs.jsonl
runs-state/
hook-state/
pack/
"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))


def ensure_state_dir(project: Project) -> Path:
    project.state.mkdir(parents=True, exist_ok=True)
    gi = project.state / ".gitignore"
    if not gi.exists():
        gi.write_text(STATE_GITIGNORE, encoding="utf-8")
    return project.state


def load(project: Project) -> dict[str, Any]:
    p = project.state / INSTALLED
    if not p.exists():
        return {"version": None, "tools": [], "files": {}, "templates": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("files", {})
    data.setdefault("templates", {})
    data.setdefault("tools", [])
    return data


def save(project: Project, data: dict[str, Any]) -> None:
    ensure_state_dir(project)
    (project.state / INSTALLED).write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
