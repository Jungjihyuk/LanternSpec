"""Bundled resources: base templates, skill sources, agent rules."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def path(rel: str) -> Path:
    return ROOT / rel


def read_text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def iter_files(rel_dir: str) -> Iterator[tuple[str, Path]]:
    base = ROOT / rel_dir
    for p in sorted(base.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".py":
            yield str(p.relative_to(base)), p
