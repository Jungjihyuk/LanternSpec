"""Bundled resources: base templates, skill sources, agent rules, principle tables."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def path(rel: str) -> Path:
    """Return the path of a bundled resource.

    Args:
        rel: Path inside the resources folder, e.g. "skills/l-build".

    Returns:
        The absolute path (it may not exist).

    Example:
        >>> path("skills/l-build").name
        'l-build'
    """
    return ROOT / rel


def read_text(rel: str) -> str:
    """Read a bundled text resource as UTF-8.

    Args:
        rel: Path inside the resources folder.

    Returns:
        The text.

    Raises:
        OSError: The resource does not exist.

    Example:
        >>> read_text("agents/AGENTS.md").startswith("#")
        True
    """
    return (ROOT / rel).read_text(encoding="utf-8")


def iter_files(rel_dir: str) -> Iterator[tuple[str, Path]]:
    """Yield the files of a bundled resource folder (Python files and caches left out), sorted.

    Args:
        rel_dir: Folder inside the resources folder, e.g. "templates".

    Yields:
        (path relative to that folder, absolute path).

    Example:
        >>> any(rel == "기획.md" for rel, _ in iter_files("templates"))
        True
    """
    base = ROOT / rel_dir
    for p in sorted(base.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".py":
            yield str(p.relative_to(base)), p
