"""Decide which folders of a knowledge store are open (knowledge.allow · knowledge.deny).

Responsibilities:
    - turn the two lists of lantern.yaml into one answer: may this path be opened?
    - say where a walk of the store may start

Not here:
    - reading and writing the store's files → learn/knowledge/obsidian.py
    - keeping an AI tool out of the closed folders at the OS level → tools/guard.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...core.project import nfc


def _parts(path: str) -> tuple[str, ...]:
    """Split a store-relative path into comparable parts (NFC, lower case, no empty or "." parts)."""
    return tuple(p.casefold() for p in nfc(str(path)).replace("\\", "/").split("/") if p and p != ".")


def _under(parts: tuple[str, ...], folders: tuple[str, ...]) -> bool:
    """Whether the path is one of the folders or inside one."""
    return any(parts[: len(f)] == f for f in (_parts(folder) for folder in folders) if f)


@dataclass(frozen=True)
class Access:
    """Which folders of a knowledge store may be opened.

    With neither list the whole store is open, as before. Once either list is set, hidden
    files and folders (`.git`, `.obsidian` …) are closed too: they often hold copies of the closed notes.

    Attributes:
        allow: Folders that are open, relative to the store root; empty means everything not denied.
        deny: Folders that are closed; they win over `allow`.

    Example:
        >>> Access(deny=("4. Work",)).permits("2. Study/JWT.md")
        True
        >>> Access(allow=("2. Study",)).permits("3. Projects/앱.md")
        False
    """

    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, knowledge: dict[str, Any]) -> Access:
        """Read the two lists from the knowledge block of lantern.yaml.

        Args:
            knowledge: The knowledge settings.

        Returns:
            The access rules; open to everything when neither list is set.

        Example:
            >>> Access.from_config({"path": "~/vault", "deny": ["4. Work"]}).deny
            ('4. Work',)
        """
        return cls(allow=tuple(str(f) for f in knowledge.get("allow") or []), deny=tuple(str(f) for f in knowledge.get("deny") or []))

    @property
    def restricted(self) -> bool:
        """Whether any folder is closed."""
        return bool(self.allow or self.deny)

    def permits(self, path: str) -> bool:
        """Say whether a path of the store may be opened.

        Names compare without regard to case or Unicode form, as macOS file names do.

        Args:
            path: A file or folder, relative to the store root.

        Returns:
            True when the path is open.

        Example:
            >>> access = Access(allow=("2. Study",), deny=("2. Study/Exam",))
            >>> access.permits("2. study/Backend/JWT.md"), access.permits("2. Study/Exam/기출.md")
            (True, False)
            >>> Access(deny=("4. Work",)).permits(".git/config"), Access().permits(".git/config")
            (False, True)
        """
        if not self.restricted:
            return True
        parts = _parts(path)
        if ".." in parts or any(p.startswith(".") for p in parts):
            return False
        if _under(parts, self.deny):
            return False
        return not self.allow or _under(parts, self.allow)

    def roots(self) -> list[str]:
        """List the folders a walk of the store may start from.

        A walk must not start at the store root when only some folders are open:
        under `lantern guard` the root itself cannot be read.

        Returns:
            The open folders (one inside another is left out); [""] — the store root — when `allow` is empty.

        Example:
            >>> Access(allow=("2. Study", "2. Study/Backend", "3. Projects"), deny=("3. Projects",)).roots()
            ['2. Study']
            >>> Access(deny=("4. Work",)).roots()
            ['']
        """
        if not self.allow:
            return [""]
        roots: list[str] = []
        for folder in sorted(self.allow, key=lambda f: len(_parts(f))):
            if self.permits(folder) and not _under(_parts(folder), tuple(roots)):
                roots.append(folder)
        return roots
