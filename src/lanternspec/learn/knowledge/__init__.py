"""Knowledge connector — the same four questions for any knowledge store.

| contract | question                               | returns                                          |
| search   | is there a note about this term?       | list of title · location · summary · modified     |
| read     | what does this note say?               | body                                             |
| propose  | may I make a note on this topic?       | a draft (waiting for approval)                   |
| write    | (after approval) make the note         | where it was made (stores that refuse writes say no) |

The contract (names · inputs · outputs) is fixed; skills reach it through `lantern knowledge …`
CLI commands, and `lantern mcp` serves the same functions as an MCP server.
We never change the other store's structure: counts and status live in our ledger.

Not here:
    - drafts waiting for approval (propose · write) → learn/knowledge/drafts.py
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from ...core.messages import msg
from ...core.project import Project


@dataclass
class Hit:
    """One note found by search.

    Attributes:
        title: The note's title.
        path: Where it is, relative to the store root (a page ID for Notion).
        summary: A short summary (for Notion, the page URL).
        updated: Last modified date (YYYY-MM-DD).
        score: How well it matched; higher is better.

    Example:
        >>> Hit("JWT", "개발/JWT.md", "토큰 형식", "2026-10-28", 100).to_dict()["path"]
        '개발/JWT.md'
    """

    title: str
    path: str  # relative to the store root
    summary: str
    updated: str
    score: int

    def to_dict(self) -> dict:
        """Return the hit as a plain mapping, for JSON output.

        Returns:
            Field name → value.

        Example:
            >>> sorted(Hit("JWT", "JWT.md", "", "", 1).to_dict())
            ['path', 'score', 'summary', 'title', 'updated']
        """
        return asdict(self)


class Adapter:
    """The contract every knowledge store implements.

    search and read are required; write is required only for stores that can be written;
    areas has a default that finds nothing.

    Attributes:
        name: The store kind, as in lantern.yaml `knowledge.type`.

    Example:
        >>> Adapter().areas("개발")
        []
    """

    name = "base"

    def search(self, query: str, aliases: list[str] | None = None, limit: int = 5) -> list[Hit]:
        """Find notes about a term.

        Args:
            query: The term.
            aliases: Other names for the term.
            limit: Most results to return.

        Returns:
            The best matches, best first.

        Raises:
            KnowledgeError: The store cannot be reached.

        Example:
            >>> adapter_for(project).search("JWT")[0].title  # doctest: +SKIP
            'JWT'
        """
        raise NotImplementedError

    def read(self, path: str) -> str:
        r"""Read one note.

        Args:
            path: The note's location, as search returned it.

        Returns:
            The note's text.

        Raises:
            KnowledgeError: The note does not exist or the store cannot be reached.

        Example:
            >>> adapter_for(project).read("개발/JWT.md")  # doctest: +SKIP
            '# JWT\n…'
        """
        raise NotImplementedError

    def write(self, rel_path: str, content: str) -> str:
        r"""Create a new note (only after a person approved it). Existing notes are never overwritten.

        Args:
            rel_path: Where to create it, relative to the store root.
            content: The note's text.

        Returns:
            Where it was created.

        Raises:
            KnowledgeError: The store refuses writes, the path is outside it, or a note is already there.

        Example:
            >>> adapter_for(project).write("개발/JWT.md", "# JWT\n")  # doctest: +SKIP
            '개발/JWT.md'
        """
        raise NotImplementedError

    def areas(self, folder: str) -> list[str]:
        """List the topic folders under a folder, to suggest topics for debt cards.

        Args:
            folder: A folder of the store, from `knowledge.areas_from`.

        Returns:
            Folder names; empty for stores without folders.

        Example:
            >>> adapter_for(project).areas("개발")  # doctest: +SKIP
            ['백엔드', '프론트']
        """
        return []


class KnowledgeError(RuntimeError):
    """A knowledge store could not do what was asked; the message says why.

    Example:
        >>> str(KnowledgeError("저장소 밖에는 쓸 수 없습니다"))
        '저장소 밖에는 쓸 수 없습니다'
    """

    pass


def adapter_for(project: Project) -> Adapter:
    """Return the adapter for the project's knowledge store.

    Args:
        project: The project.

    Returns:
        The adapter for `knowledge.type` (obsidian and folder share one).

    Raises:
        KnowledgeError: No store is set up, its folder or token is missing, or the type is unknown.

    Example:
        >>> adapter_for(project).name  # doctest: +SKIP
        'obsidian'
    """
    k = project.profile.knowledge
    if not k:
        raise KnowledgeError(msg("No knowledge store is set up (the knowledge block in lantern.yaml)"))
    kind = k["type"]
    if kind in ("obsidian", "folder"):  # folder = any Markdown folder (other stores)
        from .obsidian import ObsidianAdapter

        return ObsidianAdapter(Path(str(k["path"])).expanduser())
    if kind == "notion":
        from .notion import from_config

        return from_config(k)
    raise KnowledgeError(msg("No '{kind}' adapter (available: obsidian · folder · notion)", kind=kind))
