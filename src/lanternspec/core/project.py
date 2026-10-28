"""Where things live in a LanternSpec project, and small git helpers.

Responsibilities:
    - find the project root and build paths from lantern.yaml (docs root, numbered folders, state folder)
    - iterate documents and find works and documents by ID
    - small shared helpers: NFC names, dates, safe file names, reading and writing UTF-8, wikilinks
    - run git with stable settings (UTF-8 paths, C locale)

Not here:
    - reading and writing lantern.yaml itself → core/profile.py
    - assigning new IDs → core/new_id.py
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import subprocess
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from . import enums as enums_mod
from . import frontmatter
from . import names as names_mod
from . import profile as profile_mod
from .profile import Profile

STATE_DIR = ".lantern"


def nfc(s: str) -> str:
    """Normalize text to NFC so Korean file names from macOS compare equal.

    Args:
        s: Any text, often a file name.

    Returns:
        The NFC form of the text.

    Example:
        >>> import unicodedata
        >>> nfc(unicodedata.normalize("NFD", "기록")) == "기록"
        True
    """
    return unicodedata.normalize("NFC", s)


def today() -> str:
    """Return today's date in ISO form.

    Returns:
        The local date as "YYYY-MM-DD".

    Example:
        >>> len(today())
        10
    """
    return _dt.date.today().isoformat()


def now_minute() -> str:
    """Return the current local time to the minute, as written into documents.

    Returns:
        The time as "YYYY-MM-DD HH:MM".

    Example:
        >>> len(now_minute())
        16
    """
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def now_iso() -> str:
    """Return the current time with its UTC offset, as written into run logs.

    Returns:
        An ISO 8601 timestamp to the second, e.g. "2026-10-28T09:00:00+09:00".

    Example:
        >>> now_iso()[10]
        'T'
    """
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


_UNSAFE = re.compile(r'[\\/:*?"<>|#^\[\]]+')


def safe_name(name: str) -> str:
    """Turn a title into a name that is safe for files and Obsidian links.

    Characters that break paths or links (`/ : * ? " < > | # ^ [ ]` and the backslash) become spaces,
    runs of spaces collapse, and the result is cut to 80 characters.

    Args:
        name: A title written by a person.

    Returns:
        The cleaned name; "제목 없음" when nothing is left.

    Example:
        >>> safe_name("로그인 / 카카오: 1차")
        '로그인 카카오 1차'
        >>> safe_name("///")
        '제목 없음'
    """
    cleaned = _UNSAFE.sub(" ", nfc(name)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80].strip() or "제목 없음"


def git(args: list[str], cwd: Path, check: bool = False, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a git command with stable settings and capture its output.

    Paths are not quoted (`core.quotepath=false`) and the locale defaults to C.UTF-8,
    so Korean paths and messages come back as plain text.

    Args:
        args: git arguments, without the leading "git".
        cwd: Folder to run in.
        check: Raise when git exits with an error.
        env: Extra environment variables.

    Returns:
        The finished process, with text stdout and stderr.

    Raises:
        subprocess.CalledProcessError: check is True and git failed.

    Example:
        >>> git(["--version"], Path(".")).stdout.startswith("git version")  # doctest: +SKIP
        True
    """
    full_env = dict(os.environ)
    full_env.setdefault("LC_ALL", "C.UTF-8")
    if env:
        full_env.update(env)
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
        env=full_env,
    )


def git_out(args: list[str], cwd: Path) -> str:
    """Run a git command and return its trimmed output.

    Args:
        args: git arguments, without the leading "git".
        cwd: Folder to run in.

    Returns:
        The trimmed stdout; an empty string when git failed.

    Example:
        >>> git_out(["rev-parse", "--abbrev-ref", "HEAD"], Path("."))  # doctest: +SKIP
        'main'
    """
    r = git(args, cwd)
    return r.stdout.strip() if r.returncode == 0 else ""


def git_version(cwd: Path) -> tuple:
    """Return the installed git version as numbers.

    Args:
        cwd: Folder to run git in.

    Returns:
        (major, minor, patch); (0, 0, 0) when git is missing or the output is unexpected.

    Example:
        >>> git_version(Path(".")) >= (2, 5, 0)  # doctest: +SKIP
        True
    """
    out = git_out(["--version"], cwd)
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out)
    if not m:
        return (0, 0, 0)
    return tuple(int(x or 0) for x in m.groups())


def find_root(start: Path | None = None) -> Path:
    """Find the project root for a folder.

    Args:
        start: Folder to start from; the current folder when None.

    Returns:
        The nearest folder (start or a parent) with lantern.yaml; otherwise the git top level
        (or, inside a local-mode docs worktree, the code root above it); otherwise start itself.

    Example:
        >>> find_root(Path("my-app/src"))  # doctest: +SKIP
        PosixPath('/Users/me/my-app')
    """
    start = (start or Path.cwd()).resolve()
    for p in [start, *start.parents]:
        if (p / profile_mod.PROFILE_FILE).exists():
            return p
    top = git_out(["rev-parse", "--show-toplevel"], start)
    if top:
        top_path = Path(top)
        # inside a local-mode docs worktree: the code root is the parent of docs/
        common = git_out(["rev-parse", "--path-format=absolute", "--git-common-dir"], start)
        if common and Path(common).parent != top_path and (Path(common).parent / profile_mod.PROFILE_FILE).exists():
            return Path(common).parent
        return top_path
    return start


@dataclass
class Project:
    """One LanternSpec project: its root folder and its lantern.yaml.

    Every path the scripts use is built here; folder and file names come from names.yaml (core/names.py).

    Attributes:
        root: Project root folder.
        profile: The settings read from lantern.yaml.

    Example:
        >>> project = Project.load()  # doctest: +SKIP
        >>> project.rel(project.folder("works"))  # doctest: +SKIP
        'docs/2. 작업'
    """

    root: Path
    profile: Profile

    @classmethod
    def load(cls, root: Path | None = None) -> Project:
        """Load the project that contains a folder.

        Args:
            root: The project root; when None it is found from the current folder (find_root).

        Returns:
            The project, with lantern.yaml read (defaults when the file is missing).

        Example:
            >>> Project.load(Path("my-app")).root.name  # doctest: +SKIP
            'my-app'
        """
        r = find_root(root) if root is None else Path(root).resolve()
        return cls(root=r, profile=profile_mod.load(r))

    # ---- folders
    @property
    def docs(self) -> Path:
        """The documents root (`docs` unless lantern.yaml says otherwise)."""
        return self.root / self.profile.docs_root

    def folder(self, key: str) -> Path:
        """Return one of the numbered document folders.

        Args:
            key: Folder key from names.yaml, e.g. "works" or "templates".

        Returns:
            The folder path under the documents root (it may not exist yet).

        Raises:
            KeyError: The key is not in names.yaml.

        Example:
            >>> Project.load().folder("templates").name  # doctest: +SKIP
            '0. 템플릿'
        """
        return self.docs / self.names.folder(key)

    @property
    def templates_dir(self) -> Path:
        """The project's template folder (`docs/0. 템플릿`)."""
        return self.folder("templates")

    @property
    def enums_file(self) -> Path:
        """The project's enums.yaml (`docs/0. 템플릿/_meta/enums.yaml`)."""
        return self.templates_dir / "_meta" / "enums.yaml"

    @cached_property
    def enums(self) -> enums_mod.Enums:
        """The project's choice lists (its own enums.yaml, else the bundled one), read once per command."""
        return enums_mod.load(self.enums_file, self.profile.language)

    @cached_property
    def names(self) -> names_mod.Names:
        """Every name the program uses for this project (names.yaml of its language plus its own section decisions)."""
        return self.profile.names

    def doc_path(self, folder: Path, role: str) -> Path:
        """Return the path of a named document inside a folder.

        Args:
            folder: The folder, e.g. a work folder.
            role: Document role, e.g. "plan".

        Returns:
            `folder / <name>.md`.

        Example:
            >>> project.doc_path(work, "plan").name  # doctest: +SKIP
            '기획.md'
        """
        return folder / self.names.file(role)

    def reload_enums(self) -> None:
        """Forget the cached choice lists so the next access reads enums.yaml again.

        Call this after enums.yaml was changed within the same command.

        Example:
            >>> project.reload_enums()  # doctest: +SKIP
        """
        self.__dict__.pop("enums", None)

    @property
    def moc(self) -> Path:
        """The document map (MOC) file at the documents root."""
        return self.docs / self.names.file("moc")

    @property
    def state(self) -> Path:
        """The local state folder (`.lantern`)."""
        return self.root / STATE_DIR

    def rel(self, path: Path) -> str:
        """Return a path relative to the project root, for messages.

        Args:
            path: Any path.

        Returns:
            The NFC path relative to the root; the path unchanged when it is outside the project.

        Example:
            >>> project.rel(project.root / "docs" / "기록.md")  # doctest: +SKIP
            'docs/기록.md'
        """
        try:
            return nfc(str(Path(path).resolve().relative_to(self.root.resolve())))
        except ValueError:
            return nfc(str(path))

    def docs_rel(self, path: Path) -> str:
        """Return a path relative to the documents root, as Obsidian links use it.

        Args:
            path: Any path.

        Returns:
            The NFC path relative to the documents root; the path unchanged when it is outside it.

        Example:
            >>> project.docs_rel(project.docs / "2. 작업" / "W-012 로그인")  # doctest: +SKIP
            '2. 작업/W-012 로그인'
        """
        try:
            return nfc(str(Path(path).resolve().relative_to(self.docs.resolve())))
        except ValueError:
            return nfc(str(path))

    # ---- iteration
    def iter_docs(self, include_templates: bool = False, include_legacy: bool = False) -> Iterator[Path]:
        """Yield every Markdown document under the documents root, sorted by path.

        Hidden folders (such as `.obsidian`) are always skipped.

        Args:
            include_templates: Also yield the files in the template folder.
            include_legacy: Also yield the original documents kept in the legacy folder.

        Yields:
            Paths of `.md` files.

        Example:
            >>> [project.docs_rel(p) for p in project.iter_docs()][:1]  # doctest: +SKIP
            ['1. 아이디어/IDEA-001 카카오 로그인.md']
        """
        if not self.docs.exists():
            return
        tmpl = self.templates_dir.resolve()
        legacy = self.folder("legacy").resolve()
        for p in sorted(self.docs.rglob("*.md")):
            rp = p.resolve()
            if any(part.startswith(".") for part in p.relative_to(self.docs).parts):
                continue
            if not include_templates and (rp == tmpl or tmpl in rp.parents):
                continue
            if not include_legacy and (rp == legacy or legacy in rp.parents):
                continue
            yield p

    def work_dirs(self, include_archive: bool = False) -> list[Path]:
        """List the work folders (`W-012 이름`), sorted by name.

        Args:
            include_archive: Also list the works moved to the archive folder.

        Returns:
            The work folder paths.

        Example:
            >>> [p.name for p in project.work_dirs()]  # doctest: +SKIP
            ['W-001 카카오 로그인', 'W-002 프로필']
        """
        out: list[Path] = []
        base = self.folder("works")
        if base.exists():
            out += sorted(p for p in base.iterdir() if p.is_dir() and _WORK_DIR.match(nfc(p.name)))
        if include_archive and self.folder("archive").exists():
            out += sorted(p for p in self.folder("archive").iterdir() if p.is_dir() and _WORK_DIR.match(nfc(p.name)))
        return out

    def find_work(self, work_id: str, include_archive: bool = True) -> Path | None:
        """Find a work folder by its ID.

        Args:
            work_id: Work ID such as "W-012" (case does not matter).
            include_archive: Also look in the archive folder.

        Returns:
            The work folder; None when there is no such work.

        Example:
            >>> project.find_work("w-001").name  # doctest: +SKIP
            'W-001 카카오 로그인'
        """
        work_id = work_id.upper()
        for p in self.work_dirs(include_archive=include_archive):
            if nfc(p.name).split(" ")[0].upper() == work_id:
                return p
        return None

    def find_by_id(self, doc_id: str) -> Path | None:
        """Find a document by its ID — first by file name, then by the `id` frontmatter field.

        Documents inside a work folder (design, tasks, record) share the work's ID, so the
        frontmatter search skips them and only finds the document that owns the ID.

        Args:
            doc_id: Document ID such as "ADR-004" or "D-007" (case does not matter).

        Returns:
            The document path; None when nothing has that ID.

        Example:
            >>> project.find_by_id("D-007").name  # doctest: +SKIP
            'D-007 JWT.md'
        """
        doc_id = doc_id.upper()
        for p in self.iter_docs():
            name = nfc(p.stem)
            if name.split(" ")[0].upper() == doc_id:
                return p
        for p in self.iter_docs():
            meta = frontmatter.parse(p.read_text(encoding="utf-8")).meta
            if str(meta.get("id", "")).upper() == doc_id and meta.get("type") not in ("design", "tasks", "record"):
                return p
        return None

    def is_local_mode(self) -> bool:
        """Tell whether documents are kept out of the shared repository (`docs-mode local`).

        Returns:
            True when lantern.yaml sets remote to "local".

        Example:
            >>> project.is_local_mode()  # doctest: +SKIP
            False
        """
        return self.profile.remote == "local"

    def docs_git_cwd(self) -> Path:
        """Return where to run git for documents.

        Returns:
            The docs worktree in local mode (when it exists); otherwise the project root.

        Example:
            >>> project.docs_git_cwd() == project.root  # doctest: +SKIP
            True
        """
        return self.docs if self.is_local_mode() and (self.docs / ".git").exists() else self.root


_WORK_DIR = re.compile(r"^W-\d{3,}( |$)")


def work_id_of(path: Path) -> str:
    """Return the work ID from a work folder name.

    Args:
        path: A work folder such as `W-012 로그인`.

    Returns:
        The first word of the folder name.

    Example:
        >>> work_id_of(Path("docs/2. 작업/W-012 카카오 로그인"))
        'W-012'
    """
    return nfc(path.name).split(" ")[0]


def work_name_of(path: Path) -> str:
    """Return the work name from a work folder name.

    Args:
        path: A work folder such as `W-012 로그인`.

    Returns:
        Everything after the ID; an empty string when the folder has only the ID.

    Example:
        >>> work_name_of(Path("W-012 카카오 로그인"))
        '카카오 로그인'
        >>> work_name_of(Path("W-012"))
        ''
    """
    parts = nfc(path.name).split(" ", 1)
    return parts[1] if len(parts) > 1 else ""


def read(path: Path) -> str:
    r"""Read a text file as UTF-8.

    Args:
        path: File to read.

    Returns:
        The file's text.

    Raises:
        OSError: The file cannot be read.

    Example:
        >>> read(Path("docs/기록.md"))  # doctest: +SKIP
        '---\ntype: record\n...'
    """
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    r"""Write a text file as UTF-8, creating its folders.

    Args:
        path: File to write (replaced when it exists).
        text: The whole new text.

    Example:
        >>> write(Path("docs/2. 작업/W-012 로그인/기록.md"), "# 기록\n")  # doctest: +SKIP
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def wikilink(project: Project, path: Path, alias: str | None = None, table: bool = False) -> str:
    r"""Build an Obsidian link to a document, relative to the documents root.

    Args:
        project: The project.
        path: Document to link to (the `.md` suffix is dropped).
        alias: Text to show instead of the path.
        table: Escape the alias bar (`\|`) so the link works inside a table cell.

    Returns:
        A `[[path]]` or `[[path|alias]]` link.

    Example:
        >>> p = Project(root=Path("/p"), profile=Profile(data={}))
        >>> wikilink(p, Path("/p/docs/2. 작업/W-012 로그인/기록.md"), "기록")
        '[[2. 작업/W-012 로그인/기록|기록]]'
        >>> wikilink(p, Path("/p/docs/기록.md"), "기록", table=True)
        '[[기록\\|기록]]'
    """
    rel = project.docs_rel(path)
    if rel.endswith(".md"):
        rel = rel[:-3]
    bar = "\\|" if table else "|"
    return f"[[{rel}{bar}{alias}]]" if alias else f"[[{rel}]]"
