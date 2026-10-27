"""`lantern docs-mode local|shared` — 문서 저장 방식 바꾸기 (C-10).

local = the same repository's orphan branch `docs-local`, checked out at docs/ as a worktree:
    git worktree add --orphan -b docs-local docs
plus `.gitignore: docs/`, `.ignore: !docs/` (R2 — ripgrep searches docs/ again) and a
pre-push hook that refuses to push docs-local (R6). Never switch by hand.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ..core import profile as profile_mod
from ..core.project import Project, git, git_out, git_version, read, write

DOCS_BRANCH = "docs-local"
MIN_GIT = (2, 42, 0)
SKIP = {"LANTERN_SKIP_HOOKS": "1"}


class ModeError(RuntimeError):
    pass


def _lines(path: Path) -> list[str]:
    return read(path).split("\n") if path.exists() else []


def ensure_line(path: Path, line: str) -> bool:
    lines = _lines(path)
    if any(l.strip() == line for l in lines):
        return False
    text = read(path) if path.exists() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    write(path, text + line + "\n")
    return True


def remove_line(path: Path, line: str) -> bool:
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
    return [f"✔ 스킬 · AGENTS.md 다시 생성 ({len(rep.written)}개, docs.remote 반영)"]


def docs_pattern(project: Project) -> str:
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
    if git_version(project.root) < MIN_GIT:
        raise ModeError(f"local 방식은 git {'.'.join(map(str, MIN_GIT))} 이상이 필요합니다 (git worktree --orphan)")
    if git(["rev-parse", "--git-dir"], project.root).returncode != 0:
        raise ModeError("git 저장소가 아닙니다")
    docs = project.docs
    if (docs / ".git").exists():
        raise ModeError("이미 docs/ 안에 .git이 있습니다 — lantern doctor로 점검하세요")
    if git(["rev-parse", "--verify", "--quiet", f"refs/heads/{DOCS_BRANCH}"], project.root).returncode == 0:
        raise ModeError(f"{DOCS_BRANCH} 브랜치가 이미 있습니다 — 다시 펼치려면: git worktree add {docs.name} {DOCS_BRANCH}")
    msgs: list[str] = []
    if commit and git_out(["diff", "--cached", "--name-only"], project.root):
        commit = False  # never sweep the user's staged changes into our structure commit
        msgs.append("ℹ 이미 스테이징된 변경이 있어 구조 변경은 커밋하지 않고 스테이징만 합니다")
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
            raise ModeError(f"docs-local 브랜치를 만들지 못했습니다: {r.stderr.strip()}")
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
    msgs.append(f"✔ {DOCS_BRANCH} 빈 브랜치를 docs/에 펼침 (저장소는 하나)")
    if any(p.name != ".git" for p in docs.iterdir()):
        git(["add", "-A"], docs)
        git(["commit", "-q", "-m", "docs: 문서를 docs-local 브랜치로 옮김 [lantern]"], docs, env=SKIP)
        msgs.append("✔ 기존 문서를 docs-local에 첫 커밋")
    if ensure_line(project.root / ".gitignore", docs_pattern(project)):
        msgs.append("✔ .gitignore에 docs/ 추가 (R1)")
    if ensure_line(project.root / ".ignore", "!" + docs_pattern(project)):
        msgs.append("✔ .ignore에 !docs/ 추가 — AI 검색이 문서를 찾게 (R2)")
    _set_remote(project, "local")
    msgs.append("✔ lantern.yaml docs.remote: local")
    from ..check.githooks import install as install_hooks

    msgs += install_hooks(project)
    paths = [p for p in [".gitignore", ".ignore", profile_mod.PROFILE_FILE] if (project.root / p).exists()]
    git(["add", "--", *paths], project.root)
    msgs += _regenerate(project)
    if commit:
        # no pathspec: `git commit -- docs/` would re-stage docs/ from the working tree
        r = git(["commit", "-q", "-m", "chore: 문서를 docs-local 브랜치로 분리 [lantern]"], project.root, env=SKIP)
        if r.returncode == 0:
            msgs.append("✔ 코드 브랜치에 구조 변경 커밋")
    return msgs


def to_shared(project: Project, commit: bool = True) -> list[str]:
    docs = project.docs
    if not (docs / ".git").is_file():
        raise ModeError("docs/가 docs-local worktree가 아닙니다 — 이미 shared인지 lantern doctor로 확인하세요")
    msgs: list[str] = []
    if commit and git_out(["diff", "--cached", "--name-only"], project.root):
        commit = False
        msgs.append("ℹ 이미 스테이징된 변경이 있어 구조 변경은 커밋하지 않고 스테이징만 합니다")
    if git_out(["status", "--porcelain"], docs):
        git(["add", "-A"], docs)
        git(["commit", "-q", "-m", "docs: shared로 합치기 전 저장 [lantern]"], docs, env=SKIP)
        msgs.append("✔ docs-local의 남은 변경을 커밋")
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
            raise ModeError(f"docs worktree를 정리하지 못했습니다: {r.stderr.strip()}")
        docs.mkdir(parents=True, exist_ok=True)
        for item in list(tmp.iterdir()):
            shutil.move(str(item), str(docs / item.name))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    msgs.append(f"✔ 문서를 코드 브랜치의 docs/로 옮김 ({DOCS_BRANCH} 브랜치는 기록으로 남겨 둠)")
    if remove_line(project.root / ".gitignore", docs_pattern(project)):
        msgs.append("✔ .gitignore에서 docs/ 제거")
    if remove_line(project.root / ".ignore", "!" + docs_pattern(project)):
        msgs.append("✔ .ignore에서 !docs/ 제거")
    _set_remote(project, "shared")
    msgs.append("✔ lantern.yaml docs.remote: shared")
    git(["add", "-A", "--", docs_pattern(project)], project.root)
    for p in [".gitignore", ".ignore", profile_mod.PROFILE_FILE]:
        # removed files only exist in the index; untouched ones only on disk
        if (project.root / p).exists() or git_out(["ls-files", "--", p], project.root):
            git(["add", "-A", "--", p], project.root)
    msgs += _regenerate(project)
    if commit:
        r = git(["commit", "-q", "-m", "chore: 문서를 코드 브랜치로 합침 [lantern]"], project.root, env=SKIP)
        if r.returncode == 0:
            msgs.append("✔ 코드 브랜치에 문서 커밋")
    return msgs
