"""`lantern docs-mode local|shared` — switch how documents are stored.

local = the same repository's orphan branch `docs-local`, checked out at docs/ as a worktree:
    git worktree add --orphan -b docs-local docs
plus `.gitignore: docs/`, `.ignore: !docs/` (so ripgrep searches docs/ again) and a
pre-push hook that refuses to push docs-local. Never switch by hand.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ..core import profile as profile_mod
from ..core.messages import msg
from ..core.project import Project, git, git_out, git_version, read, write

DOCS_BRANCH = "docs-local"
MIN_GIT = (2, 42, 0)
SKIP = {"LANTERN_SKIP_HOOKS": "1"}


class ModeError(RuntimeError):
    """The storage mode could not be switched; the message says why and what to do.

    Example:
        >>> str(ModeError("git 저장소가 아닙니다"))
        'git 저장소가 아닙니다'
    """

    pass


def _lines(path: Path) -> list[str]:
    return read(path).split("\n") if path.exists() else []


def ensure_line(path: Path, line: str) -> bool:
    """Add a line to a text file unless it is already there (creating the file when missing).

    Args:
        path: The file, e.g. `.gitignore`.
        line: The line.

    Returns:
        True when the line was added.

    Example:
        >>> ensure_line(Path(".gitignore"), "docs/")  # doctest: +SKIP
        True
    """
    lines = _lines(path)
    if any(l.strip() == line for l in lines):
        return False
    text = read(path) if path.exists() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    write(path, text + line + "\n")
    return True


def remove_line(path: Path, line: str) -> bool:
    """Remove a line from a text file (deleting the file when nothing is left).

    Args:
        path: The file.
        line: The line.

    Returns:
        True when the line was removed.

    Example:
        >>> remove_line(Path(".gitignore"), "docs/")  # doctest: +SKIP
        True
    """
    if not path.exists():
        return False
    lines = _lines(path)
    kept = [l for l in lines if l.strip() != line]
    if kept == lines:
        return False
    text = "\n".join(kept)
    if not text.strip():
        path.unlink()
    else:
        write(path, text)
    return True


def _regenerate(project: Project) -> list[str]:
    """Skills and AGENTS.md render differently per docs.remote — refresh them (if installed)."""
    from ..core import state
    from .install import install

    if not state.load(project).get("version"):
        return []
    rep = install(project)
    changed = [p for p in rep.written] + ["AGENTS.md", ".lantern/installed.json"]
    for rel in changed:
        if (project.root / rel).exists():
            git(["add", "--", rel], project.root)
    return [msg("✔ Regenerated skills · AGENTS.md ({count}, with docs.remote)", count=len(rep.written))]


def docs_pattern(project: Project) -> str:
    """Return the documents root as an ignore pattern.

    Args:
        project: The project.

    Returns:
        The root with a trailing slash, e.g. "docs/".

    Example:
        >>> docs_pattern(project)  # doctest: +SKIP
        'docs/'
    """
    return project.profile.docs_root.rstrip("/") + "/"


def _set_remote(project: Project, value: str) -> None:
    path = project.root / profile_mod.PROFILE_FILE
    if path.exists():
        new = profile_mod.set_in_text(read(path), "docs.remote", value)
        if new is not None:
            write(path, new)
        else:
            data = profile_mod.load(project.root).data
            data["docs"]["remote"] = value
            profile_mod.save(project.root, data)
    project.profile.data["docs"]["remote"] = value


def to_local(project: Project, commit: bool = True) -> list[str]:
    """Move documents to the `docs-local` branch, checked out at docs/ as a worktree.

    Existing documents get a first commit there; the ignore files, lantern.yaml, git hooks and
    installed skills are updated, and the structure change is committed on the code branch
    (only staged when the user already had staged changes).

    Args:
        project: The project.
        commit: Commit the structure change on the code branch.

    Returns:
        One message per step.

    Raises:
        ModeError: git is too old, this is not a repository, docs/ already has .git, or the branch exists.

    Example:
        >>> to_local(project)[0]  # doctest: +SKIP
        '✔ docs-local 빈 브랜치를 docs/에 펼침 (저장소는 하나)'
    """
    if git_version(project.root) < MIN_GIT:
        raise ModeError(msg("The local mode needs git {items} or later (git worktree --orphan)", items=".".join(map(str, MIN_GIT))))
    if git(["rev-parse", "--git-dir"], project.root).returncode != 0:
        raise ModeError(msg("Not a git repository"))
    docs = project.docs
    if (docs / ".git").exists():
        raise ModeError(msg("docs/ already has a .git — check it with lantern doctor"))
    if git(["rev-parse", "--verify", "--quiet", f"refs/heads/{DOCS_BRANCH}"], project.root).returncode == 0:
        raise ModeError(
            msg(
                "The {docs_branch} branch already exists — to check it out again: git worktree add {name} {docs_branch}",
                docs_branch=DOCS_BRANCH,
                name=docs.name,
            )
        )
    msgs: list[str] = []
    if commit and git_out(["diff", "--cached", "--name-only"], project.root):
        commit = False  # never sweep the user's staged changes into our structure commit
        msgs.append(msg("ℹ There are staged changes already, so the layout change is only staged, not committed"))
    tmp = Path(tempfile.mkdtemp(prefix="lantern-docs-"))
    had_docs = docs.exists() and any(docs.iterdir())
    tracked = bool(git_out(["ls-files", "--", docs_pattern(project)], project.root))
    try:
        if had_docs:
            for item in list(docs.iterdir()):
                shutil.move(str(item), str(tmp / item.name))
            docs.rmdir()
        elif docs.exists():
            docs.rmdir()
        if tracked:
            git(["rm", "-r", "--cached", "--quiet", "--", docs_pattern(project)], project.root, check=True)
        r = git(["worktree", "add", "--orphan", "-b", DOCS_BRANCH, str(docs)], project.root)
        if r.returncode != 0:
            raise ModeError(msg("Couldn't create the docs-local branch: {strip}", strip=r.stderr.strip()))
        for item in list(tmp.iterdir()):
            shutil.move(str(item), str(docs / item.name))
    except Exception:
        # put the documents back no matter what
        docs.mkdir(parents=True, exist_ok=True)
        for item in list(tmp.iterdir()):
            if not (docs / item.name).exists():
                shutil.move(str(item), str(docs / item.name))
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    msgs.append(msg("✔ Checked out the empty {docs_branch} branch at docs/ (still one repository)", docs_branch=DOCS_BRANCH))
    if any(p.name != ".git" for p in docs.iterdir()):
        git(["add", "-A"], docs)
        git(["commit", "-q", "-m", msg("docs: move documents to the docs-local branch [lantern]")], docs, env=SKIP)
        msgs.append(msg("✔ First commit of the existing documents to docs-local"))
    if ensure_line(project.root / ".gitignore", docs_pattern(project)):
        msgs.append(msg("✔ Added docs/ to .gitignore"))
    if ensure_line(project.root / ".ignore", "!" + docs_pattern(project)):
        msgs.append(msg("✔ Added !docs/ to .ignore — so AI search finds the documents"))
    _set_remote(project, "local")
    msgs.append("✔ lantern.yaml docs.remote: local")
    from ..check.githooks import install as install_hooks

    msgs += install_hooks(project)
    paths = [p for p in [".gitignore", ".ignore", profile_mod.PROFILE_FILE] if (project.root / p).exists()]
    git(["add", "--", *paths], project.root)
    msgs += _regenerate(project)
    if commit:
        # no pathspec: `git commit -- docs/` would re-stage docs/ from the working tree
        r = git(["commit", "-q", "-m", msg("chore: split documents into the docs-local branch [lantern]")], project.root, env=SKIP)
        if r.returncode == 0:
            msgs.append(msg("✔ Committed the layout change on the code branch"))
    return msgs


def to_shared(project: Project, commit: bool = True) -> list[str]:
    """Move documents back into the code branch's docs/ (the `docs-local` branch is kept as history).

    Args:
        project: The project.
        commit: Commit the documents on the code branch.

    Returns:
        One message per step.

    Raises:
        ModeError: docs/ is not the docs-local worktree, or the worktree could not be removed.

    Example:
        >>> to_shared(project)[-1]  # doctest: +SKIP
        '✔ 코드 브랜치에 문서 커밋'
    """
    docs = project.docs
    if not (docs / ".git").is_file():
        raise ModeError(msg("docs/ is not the docs-local worktree — check with lantern doctor whether it's shared already"))
    msgs: list[str] = []
    if commit and git_out(["diff", "--cached", "--name-only"], project.root):
        commit = False
        msgs.append(msg("ℹ There are staged changes already, so the layout change is only staged, not committed"))
    if git_out(["status", "--porcelain"], docs):
        git(["add", "-A"], docs)
        git(["commit", "-q", "-m", msg("docs: save before merging into shared [lantern]")], docs, env=SKIP)
        msgs.append(msg("✔ Committed the remaining changes in docs-local"))
    tmp = Path(tempfile.mkdtemp(prefix="lantern-docs-"))
    try:
        for item in list(docs.iterdir()):
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.copytree(item, tmp / item.name, symlinks=True)
            else:
                shutil.copy2(item, tmp / item.name)
        r = git(["worktree", "remove", str(docs)], project.root)
        if r.returncode != 0:
            raise ModeError(msg("Couldn't remove the docs worktree: {strip}", strip=r.stderr.strip()))
        docs.mkdir(parents=True, exist_ok=True)
        for item in list(tmp.iterdir()):
            shutil.move(str(item), str(docs / item.name))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    msgs.append(
        msg("✔ Moved the documents into docs/ on the code branch (the {docs_branch} branch is kept as history)", docs_branch=DOCS_BRANCH)
    )
    if remove_line(project.root / ".gitignore", docs_pattern(project)):
        msgs.append(msg("✔ Removed docs/ from .gitignore"))
    if remove_line(project.root / ".ignore", "!" + docs_pattern(project)):
        msgs.append(msg("✔ Removed !docs/ from .ignore"))
    _set_remote(project, "shared")
    msgs.append("✔ lantern.yaml docs.remote: shared")
    git(["add", "-A", "--", docs_pattern(project)], project.root)
    for p in [".gitignore", ".ignore", profile_mod.PROFILE_FILE]:
        # removed files only exist in the index; untouched ones only on disk
        if (project.root / p).exists() or git_out(["ls-files", "--", p], project.root):
            git(["add", "-A", "--", p], project.root)
    msgs += _regenerate(project)
    if commit:
        r = git(["commit", "-q", "-m", msg("chore: merge documents into the code branch [lantern]")], project.root, env=SKIP)
        if r.returncode == 0:
            msgs.append(msg("✔ Committed the documents on the code branch"))
    return msgs
