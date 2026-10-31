"""Which folders of the project get their own rules (parts): find the candidates and record what the person decides.

A part is a folder with its own toolchain (its own manifest, e.g. backend/pyproject.toml). It gets
its own AGENTS.md with its language conventions and its own check commands; the root AGENTS.md keeps
the ways of working and a map of the parts. With fewer than two parts nothing changes.

Responsibilities:
    - list the candidates (from the files git knows) with what was decided about each
    - record a decision in lantern.yaml: add a part (with its detected languages and check commands) or ignore it
    - tell which part a file belongs to · which folder AGENTS.md files the hooks don't hand over

Not here:
    - telling a candidate from its files → core/principles.py (part_candidates)
    - writing each part's AGENTS.md → tools/rules.py · tools/install.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core import principles
from ..core import profile as profile_mod
from ..core.messages import msg
from ..core.project import Project, worktree_files


@dataclass
class PartStatus:
    """A candidate or recorded part, and what was decided about it.

    Attributes:
        path: The folder, relative to the project root.
        languages: Its languages.
        evidence: The manifest files that show it ([] for a recorded part no longer found).
        state: "added", "ignored", "new" (not decided yet) or "inside" (a folder inside a recorded part).
        owner: For "inside", the part that holds it.

    Example:
        >>> PartStatus("backend", ["python"], ["pyproject.toml"], "new").state
        'new'
    """

    path: str
    languages: list[str]
    evidence: list[str]
    state: str
    owner: str = ""


def recorded(project: Project) -> list[dict[str, Any]]:
    """The parts recorded in lantern.yaml.

    Args:
        project: The project.

    Returns:
        Each part as written (path · languages · build).

    Example:
        >>> [p["path"] for p in recorded(project)]  # doctest: +SKIP
        ['backend', 'frontend/apps/web']
    """
    return [p for p in project.profile.get("code.parts") or [] if isinstance(p, dict) and p.get("path")]


def statuses(project: Project) -> list[PartStatus]:
    """List every candidate and recorded part with what was decided.

    Args:
        project: The project.

    Returns:
        Sorted by path.

    A candidate inside a recorded part (e.g. the member frontend/apps/web of the recorded workspace
    frontend) is not asked about: the part that holds it already decides its rules.

    Example:
        >>> [(s.path, s.state) for s in statuses(project)]  # doctest: +SKIP
        [('analysis', 'ignored'), ('backend', 'added'), ('frontend', 'added'), ('frontend/apps/web', 'inside')]
    """
    files = worktree_files(project.root)
    found = {c.path: c for c in principles.part_candidates(project.root, files)}
    added = {p["path"]: p for p in recorded(project)}
    ignored = set(project.profile.get("code.ignored_parts") or [])
    out = []
    for path in sorted(set(found) | set(added)):
        owner = max((a for a in added if path.startswith(a + "/")), key=len, default="")
        if path in added:
            langs, evidence, state = list(added[path].get("languages") or []), _own_manifests(project, files, path), "added"
        else:
            cand = found[path]  # only recorded parts can be missing from the candidates
            langs, evidence = cand.languages, cand.evidence
            state = "inside" if owner else "ignored" if path in ignored else "new"
        out.append(PartStatus(path, langs, evidence, state, owner if state == "inside" else ""))
    return out


def _own_manifests(project: Project, files: list[str], path: str) -> list[str]:
    """The manifest files right in a folder (also for a workspace root, whose members are the usual candidates)."""
    own = [f for f in files if f.startswith(path + "/") and "/" not in f[len(path) + 1 :]]
    return next((c.evidence for c in principles.part_candidates(project.root, own) if c.path == path), [])


def add(project: Project, path: str) -> dict[str, Any]:
    """Record a folder as a part, with the languages and check commands found in it.

    Commands the root's lantern.yaml already runs in this folder (`cd backend && …`) are taken over,
    without the `cd`; otherwise the tools configured in the folder are recorded as they are, and a
    folder with none gets each language's default (to run from inside the folder).

    Args:
        project: The project.
        path: The folder, relative to the project root.

    Returns:
        The recorded part.

    Raises:
        ValueError: The folder has no manifest of a known language.

    Example:
        >>> add(project, "backend")["build"]["lint"]  # doctest: +SKIP
        'uv run ruff check .'
    """
    path = path.strip("/")
    found = principles.detect(project.root / path)
    if not found.languages:
        raise ValueError(
            msg("{path} has no package file of a known language (pyproject.toml · package.json …) — it can't be a part", path=path)
        )
    build = found.commands(fill_defaults=False) or found.commands(fill_defaults=True)
    build.update(_from_root(project, path))  # what a person already set for this folder wins
    part = {"path": path, "languages": found.languages, "build": build}
    parts = [p for p in recorded(project) if p["path"] != path] + [part]
    ignored = [p for p in project.profile.get("code.ignored_parts") or [] if p != path]
    _save(project, sorted(parts, key=lambda p: p["path"]), ignored)
    return part


def _from_root(project: Project, path: str) -> dict[str, str]:
    """The root's check commands that run in this folder (`cd <folder> && …`), without the `cd`."""
    prefix = f"cd {path} && "
    out = {}
    for role in (*principles.COMMAND_ROLES, "test"):
        command = str(project.profile.get(f"build.{role}") or "")
        if command.startswith(prefix) and "&&" not in command[len(prefix) :]:
            out[role] = command[len(prefix) :]
    return out


def ignore(project: Project, path: str) -> None:
    """Record that a folder is not a part (it is no longer asked about; a recorded part is dropped).

    Args:
        project: The project.
        path: The folder, relative to the project root.

    Example:
        >>> ignore(project, "analysis")  # doctest: +SKIP
    """
    path = path.strip("/")
    parts = [p for p in recorded(project) if p["path"] != path]
    ignored = sorted({*(str(x) for x in project.profile.get("code.ignored_parts") or []), path})
    _save(project, parts, ignored)


def _save(project: Project, parts: list[dict[str, Any]], ignored: list[str]) -> None:
    profile_mod.update(project.root, {"code.parts": parts, "code.ignored_parts": ignored})
    project.profile = profile_mod.load(project.root)


def part_of(project: Project, path: str, cwd: str = "") -> str | None:
    """Tell which part a file belongs to.

    Args:
        project: The project.
        path: The file, absolute or relative to cwd.
        cwd: The folder the agent works in (the project root when empty).

    Returns:
        The part's folder (the deepest that holds the file); None outside every part or with fewer than two parts.

    Example:
        >>> part_of(project, "backend/app/main.py")  # doctest: +SKIP
        'backend'
    """
    from .rules import active_parts

    target = Path(path) if Path(path).is_absolute() else Path(cwd or project.root) / path
    try:
        rel = target.resolve().relative_to(project.root.resolve()).as_posix()
    except ValueError:
        return None
    inside = [p["path"] for p in active_parts(project.profile) if rel == p["path"] or rel.startswith(p["path"] + "/")]
    return max(inside, key=len) if inside else None


def unseen_rules(project: Project, tools: list[Any]) -> tuple[list[str], list[str]]:
    """Find the folder AGENTS.md files that some installed tools never get.

    Only a part's own AGENTS.md (right in the part's folder) is handed over by the hooks. Any other
    AGENTS.md below the root reaches a tool that doesn't read folder rules by itself only when the
    tool happens to start in that folder — so people should not count on it.

    Args:
        project: The project.
        tools: The installed tool adapters.

    Returns:
        (the AGENTS.md files, the names of the tools that won't get them); both empty when all is seen.

    Example:
        >>> unseen_rules(project, resolve(["codex"]))  # doctest: +SKIP
        (['backend/app/AGENTS.md'], ['Codex'])
    """
    from .rules import active_parts, nested_agents

    blind = [t.label for t in tools if not t.reads_nested_rules]
    if not blind:
        return [], []
    roots = {f"{p['path']}/AGENTS.md" for p in active_parts(project.profile)}
    unseen = [rel for rel in nested_agents(project) if rel not in roots]
    return (unseen, blind) if unseen else ([], [])
