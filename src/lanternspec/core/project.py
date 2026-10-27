"""Where things live in a LanternSpec project, and small git helpers."""

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
from . import profile as profile_mod
from .profile import FOLDERS, MOC_FILE, Profile

STATE_DIR = ".lantern"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def today() -> str:
    return _dt.date.today().isoformat()


def now_minute() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


_UNSAFE = re.compile(r'[\\/:*?"<>|#^\[\]]+')


def safe_name(name: str) -> str:
    cleaned = _UNSAFE.sub(" ", nfc(name)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80].strip() or "제목 없음"


def git(args: list[str], cwd: Path, check: bool = False, env: dict | None = None) -> subprocess.CompletedProcess:
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
    r = git(args, cwd)
    return r.stdout.strip() if r.returncode == 0 else ""


def git_version(cwd: Path) -> tuple:
    out = git_out(["--version"], cwd)
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out)
    if not m:
        return (0, 0, 0)
    return tuple(int(x or 0) for x in m.groups())


def find_root(start: Path | None = None) -> Path:
    """Nearest folder with lantern.yaml; otherwise the git top level; otherwise cwd."""
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
    root: Path
    profile: Profile

    @classmethod
    def load(cls, root: Path | None = None) -> Project:
        r = find_root(root) if root is None else Path(root).resolve()
        return cls(root=r, profile=profile_mod.load(r))

    # ---- folders
    @property
    def docs(self) -> Path:
        return self.root / self.profile.docs_root

    def folder(self, key: str) -> Path:
        return self.docs / FOLDERS[key]

    @property
    def templates_dir(self) -> Path:
        return self.folder("templates")

    @property
    def enums_file(self) -> Path:
        return self.templates_dir / "_meta" / "enums.yaml"

    @cached_property
    def enums(self) -> enums_mod.Enums:
        """The project's choice lists (its own enums.yaml, else the bundled one) — read once per command."""
        return enums_mod.load(self.enums_file)

    def reload_enums(self) -> None:
        self.__dict__.pop("enums", None)

    @property
    def moc(self) -> Path:
        return self.docs / MOC_FILE

    @property
    def state(self) -> Path:
        return self.root / STATE_DIR

    def rel(self, path: Path) -> str:
        try:
            return nfc(str(Path(path).resolve().relative_to(self.root.resolve())))
        except ValueError:
            return nfc(str(path))

    def docs_rel(self, path: Path) -> str:
        try:
            return nfc(str(Path(path).resolve().relative_to(self.docs.resolve())))
        except ValueError:
            return nfc(str(path))

    # ---- iteration
    def iter_docs(self, include_templates: bool = False, include_legacy: bool = False) -> Iterator[Path]:
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
        out: list[Path] = []
        base = self.folder("works")
        if base.exists():
            out += sorted(p for p in base.iterdir() if p.is_dir() and _WORK_DIR.match(nfc(p.name)))
        if include_archive and self.folder("archive").exists():
            out += sorted(p for p in self.folder("archive").iterdir() if p.is_dir() and _WORK_DIR.match(nfc(p.name)))
        return out

    def find_work(self, work_id: str, include_archive: bool = True) -> Path | None:
        work_id = work_id.upper()
        for p in self.work_dirs(include_archive=include_archive):
            if nfc(p.name).split(" ")[0].upper() == work_id:
                return p
        return None

    def find_by_id(self, doc_id: str) -> Path | None:
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
        return self.profile.remote == "local"

    def docs_git_cwd(self) -> Path:
        """Where to run git for documents (docs worktree in local mode)."""
        return self.docs if self.is_local_mode() and (self.docs / ".git").exists() else self.root


_WORK_DIR = re.compile(r"^W-\d{3,}( |$)")


def work_id_of(path: Path) -> str:
    return nfc(path.name).split(" ")[0]


def work_name_of(path: Path) -> str:
    parts = nfc(path.name).split(" ", 1)
    return parts[1] if len(parts) > 1 else ""


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def wikilink(project: Project, path: Path, alias: str | None = None, table: bool = False) -> str:
    """Obsidian link from the docs root. ``table=True`` escapes the alias bar for table cells."""
    rel = project.docs_rel(path)
    if rel.endswith(".md"):
        rel = rel[:-3]
    bar = "\\|" if table else "|"
    return f"[[{rel}{bar}{alias}]]" if alias else f"[[{rel}]]"
