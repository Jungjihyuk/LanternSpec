"""`lantern work` — one work = one branch, parallel worktrees, finish, archive.

Responsibilities:
    - the `work/W-012` branch of a work, in this folder or in its own worktree
    - warn when parallel works say they will change the same tables or files
    - finish a work: test, merge into the base branch, clean up; archive its folder and fix links

Not here:
    - running the test command → report/scan.py (run_tests)
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core import frontmatter
from ..core.project import Project, git, git_out, nfc, read, work_name_of, write
from ..core.taskfile import parse_tasks

LOCKFILES = [
    ("pnpm-lock.yaml", "pnpm install --frozen-lockfile"),
    ("package-lock.json", "npm ci"),
    ("yarn.lock", "yarn install --frozen-lockfile"),
    ("bun.lockb", "bun install"),
    ("uv.lock", "uv sync"),
    ("poetry.lock", "poetry install"),
    ("Gemfile.lock", "bundle install"),
    ("Podfile.lock", "pod install"),
]


class WorkError(RuntimeError):
    """A work branch or worktree operation could not be done; the message says why and what to do.

    Example:
        >>> str(WorkError("작업 W-012 폴더가 없습니다"))
        '작업 W-012 폴더가 없습니다'
    """

    pass


def branch_name(work_id: str) -> str:
    """Return the branch name of a work.

    Args:
        work_id: The work, e.g. "w-012".

    Returns:
        "work/W-012".

    Example:
        >>> branch_name("w-012")
        'work/W-012'
    """
    return f"work/{work_id.upper()}"


def _branch_exists(project: Project, name: str) -> bool:
    return git(["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], project.root).returncode == 0


def current_branch(cwd: Path) -> str:
    """Return the checked-out branch of a folder.

    Args:
        cwd: A folder inside a git repository.

    Returns:
        The branch name ("HEAD" when detached; "" outside git).

    Example:
        >>> current_branch(Path("."))  # doctest: +SKIP
        'main'
    """
    return git_out(["rev-parse", "--abbrev-ref", "HEAD"], cwd)


def _base(project: Project) -> str:
    base = str(project.profile.get("git.base") or "main")
    if _branch_exists(project, base):
        return base
    return "HEAD"


def ensure_branch(project: Project, work_id: str) -> str:
    """Switch this folder to the work's branch, creating it from the current HEAD when needed (/l-build W-012).

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".

    Returns:
        What happened, as a message.

    Raises:
        WorkError: git could not switch or create the branch.

    Example:
        >>> ensure_branch(project, "W-012")  # doctest: +SKIP
        'work/W-012 브랜치를 만들었습니다'
    """
    name = branch_name(work_id)
    if current_branch(project.root) == name:
        return f"이미 {name} 브랜치입니다"
    if _branch_exists(project, name):
        r = git(["checkout", name], project.root)
        if r.returncode != 0:
            raise WorkError(r.stderr.strip())
        return f"{name} 브랜치로 바꿨습니다"
    r = git(["checkout", "-b", name], project.root)
    if r.returncode != 0:
        raise WorkError(r.stderr.strip())
    return f"{name} 브랜치를 만들었습니다"


# --------------------------------------------------------------------------- worktrees


@dataclass
class Worktree:
    """One git worktree.

    Attributes:
        path: Its folder.
        branch: Its branch without "refs/heads/"; "" when detached.
        head: The commit it is on.

    Example:
        >>> Worktree(Path("../app-W-012"), "work/W-012", "abc123").branch
        'work/W-012'
    """

    path: Path
    branch: str
    head: str


def worktrees(project: Project) -> list[Worktree]:
    """List the repository's worktrees (the main folder included).

    Args:
        project: The project.

    Returns:
        The worktrees, as git lists them.

    Example:
        >>> [wt.branch for wt in worktrees(project)]  # doctest: +SKIP
        ['main', 'work/W-012']
    """
    out = git_out(["worktree", "list", "--porcelain"], project.root)
    items: list[Worktree] = []
    cur: dict[str, str] = {}
    for line in out.split("\n") + [""]:
        if not line.strip():
            if cur.get("worktree"):
                items.append(Worktree(Path(cur["worktree"]), cur.get("branch", "").replace("refs/heads/", ""), cur.get("HEAD", "")))
            cur = {}
            continue
        key, _, val = line.partition(" ")
        cur[key] = val
    return items


def work_worktree(project: Project, work_id: str) -> Worktree | None:
    """Find the worktree where a work's branch is checked out.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".

    Returns:
        The worktree; None when the branch is not checked out anywhere.

    Example:
        >>> work_worktree(project, "W-012").path  # doctest: +SKIP
        PosixPath('/Users/me/app-W-012')
    """
    name = branch_name(work_id)
    for wt in worktrees(project):
        if wt.branch == name:
            return wt
    return None


def _touch_points(project: Project, work_id: str) -> set[str]:
    """Tables and files a design says it will change — for start-time conflict warnings."""
    folder = project.find_work(work_id, include_archive=False)
    if folder is None or not (folder / "설계.md").exists():
        return set()
    text = frontmatter.parse(read(folder / "설계.md")).body
    points: set[str] = set()
    for block in re.findall(r"```dbml\n(.*?)```", text, re.S):
        points |= {f"테이블 {m}" for m in re.findall(r"(?im)^\s*Table\s+\"?([\w.]+)\"?", block)}
    for m in re.findall(r"`([\w./\-]+\.[A-Za-z0-9]{1,6})`", text):
        if "/" in m and not m.startswith("화면/"):
            points.add(f"파일 {m}")
    return points


def conflicts(project: Project, work_ids: list[str]) -> list[str]:
    """Warn when works would change the same tables or files.

    The touch points come from each design: DBML tables and file paths written in backticks.
    Works already running in worktrees are compared too.

    Args:
        project: The project.
        work_ids: The works about to start.

    Returns:
        One warning per pair that shares touch points.

    Example:
        >>> conflicts(project, ["W-012", "W-013"])  # doctest: +SKIP
        ['⚠ W-012 · W-013가 같은 곳을 고칩니다: 테이블 users']
    """
    running = [wt.branch.split("/", 1)[1] for wt in worktrees(project) if wt.branch.startswith("work/")]
    ids = list(dict.fromkeys([w.upper() for w in work_ids] + running))
    points = {w: _touch_points(project, w) for w in ids}
    warnings = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            if a not in [w.upper() for w in work_ids] and b not in [w.upper() for w in work_ids]:
                continue
            common = points[a] & points[b]
            if common:
                warnings.append(f"⚠ {a} · {b}가 같은 곳을 고칩니다: {', '.join(sorted(common))}")
    return warnings


def _install(path: Path) -> str | None:
    for lock, cmd in LOCKFILES:
        if (path / lock).exists():
            r = subprocess.run(cmd, shell=True, cwd=str(path), capture_output=True, text=True)
            return f"{cmd} → {'완료' if r.returncode == 0 else '실패 (직접 확인)'}"
    return None


def start(project: Project, work_ids: list[str], install: bool = True, parent: Path | None = None) -> list[str]:
    """Start works in parallel, each in its own worktree next to the project folder.

    Each worktree gets `.env*` files copied, the docs folder linked in local mode, and
    its dependencies installed from the lock file it has.

    Args:
        project: The project.
        work_ids: The works to start, e.g. ["W-012", "W-013"].
        install: Install dependencies in each new worktree.
        parent: Folder to put the worktrees in; the project's parent when None.

    Returns:
        Messages: conflict warnings, then one line per work with how to open it.

    Raises:
        WorkError: The repository has no commit, a work folder is missing, or git failed.

    Example:
        >>> start(project, ["W-012"], install=False)[0]  # doctest: +SKIP
        '• W-012: /Users/me/app-W-012 (work/W-012)'
    """
    if git(["rev-parse", "--verify", "HEAD"], project.root).returncode != 0:
        raise WorkError("커밋이 하나도 없어 worktree를 만들 수 없습니다 — 먼저 커밋하세요")
    msgs: list[str] = []
    msgs += conflicts(project, work_ids)
    parent = parent or project.root.parent
    base = _base(project)
    for wid in work_ids:
        wid = wid.upper()
        folder = project.find_work(wid, include_archive=False)
        if folder is None:
            raise WorkError(f"작업 {wid} 폴더가 없습니다 — /l-plan 먼저")
        existing = work_worktree(project, wid)
        if existing:
            msgs.append(f"• {wid}: 이미 {existing.path}에서 진행 중")
            continue
        path = parent / f"{project.root.name}-{wid}"
        name = branch_name(wid)
        args = ["worktree", "add", str(path), name] if _branch_exists(project, name) else ["worktree", "add", "-b", name, str(path), base]
        r = git(args, project.root)
        if r.returncode != 0:
            raise WorkError(f"{wid}: worktree를 만들지 못했습니다 — {r.stderr.strip()}")
        # .env* files are untracked by design: copy them over
        for env in project.root.glob(".env*"):
            if env.is_file():
                shutil.copy2(env, path / env.name)
        docs_rel = project.profile.docs_root
        if project.is_local_mode():
            link = path / docs_rel
            if not link.exists():
                link.symlink_to(project.docs, target_is_directory=True)
        elif not (path / docs_rel / project.docs_rel(folder)).exists():
            msgs.append(f"⚠ {wid}: 작업 폴더가 아직 커밋되지 않아 worktree에 없습니다 — 문서를 먼저 커밋하세요")
        note = _install(path) if install else None
        msgs.append(f"• {wid}: {path} ({name})" + (f" · {note}" if note else ""))
        msgs.append(f'    터미널에서: cd "{path}" && claude "/l-build {wid}"')
    return msgs


def _progress(project: Project, wid: str, root: Path | None = None) -> str:
    base = Project(root=root, profile=project.profile) if root else project
    folder = base.find_work(wid, include_archive=False) if base.docs.exists() else None
    if folder is None:
        folder = project.find_work(wid, include_archive=False)
    if folder is None or not (folder / "할 일.md").exists():
        return "할 일 없음"
    ts = parse_tasks(read(folder / "할 일.md"))
    return f"{sum(t.done for t in ts)}/{len(ts)} 완료"


def list_works(project: Project) -> list[str]:
    """List the works running on their own branches, with progress and uncommitted changes.

    Args:
        project: The project.

    Returns:
        One line per work branch; a single "none" line when there are none.

    Example:
        >>> list_works(project)  # doctest: +SKIP
        ['W-012  work/W-012  /Users/me/app-W-012  1/3 완료']
    """
    out = []
    for wt in worktrees(project):
        if not wt.branch.startswith("work/"):
            continue
        wid = wt.branch.split("/", 1)[1]
        dirty = bool(git_out(["status", "--porcelain", "--untracked-files=no"], wt.path))
        out.append(f"{wid}  {wt.branch}  {wt.path}  {_progress(project, wid, wt.path)}{'  (커밋 안 된 변경 있음)' if dirty else ''}")
    for b in git_out(["branch", "--list", "work/*", "--format=%(refname:short)"], project.root).splitlines():
        if not any(wt.branch == b for wt in worktrees(project)):
            wid = b.split("/", 1)[1]
            out.append(f"{wid}  {b}  (worktree 없음)  {_progress(project, wid)}")
    return out or ["진행 중인 동시 작업이 없습니다"]


def finish(project: Project, work_id: str, test: bool = True, keep: bool = False) -> list[str]:
    """Finish a work: run the tests, merge its branch into the base branch, and clean up.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        test: Run build.test first; a failure stops the merge.
        keep: Keep the worktree and the branch after merging.

    Returns:
        Messages describing each step, ending with what to do next.

    Raises:
        WorkError: The branch is missing, there are uncommitted changes, the tests failed,
            the base branch is missing or not checked out, or the merge conflicted (it is aborted).

    Example:
        >>> finish(project, "W-012", test=False)[0]  # doctest: +SKIP
        '✔ work/W-012 → main 머지'
    """
    wid = work_id.upper()
    name = branch_name(wid)
    if not _branch_exists(project, name):
        raise WorkError(f"{name} 브랜치가 없습니다")
    msgs: list[str] = []
    wt = work_worktree(project, wid)
    in_place = wt is not None and wt.path.resolve() == project.root.resolve()
    work_path = wt.path if wt else project.root
    if git_out(["status", "--porcelain", "--untracked-files=no"], work_path):
        raise WorkError(f"{work_path}에 커밋 안 된 변경이 있습니다 — 커밋하고 다시 실행하세요")
    if test:
        cmd = project.profile.get("build.test")
        if cmd:
            from ..report.scan import run_tests

            res = run_tests(project, str(cmd), cwd=work_path)
            if not res["ok"]:
                raise WorkError(f"테스트 실패 — 머지하지 않습니다 (`{cmd}`)\n{res['tail']}")
            msgs.append(f"✔ 테스트 통과 (`{cmd}`)")
        else:
            msgs.append("ℹ build.test가 없어 테스트를 건너뜀")
    base = str(project.profile.get("git.base") or "main")
    if not _branch_exists(project, base):
        raise WorkError(f"기준 브랜치 {base}가 없습니다 (lantern.yaml git.base)")
    if in_place:
        r = git(["checkout", base], project.root)
        if r.returncode != 0:
            raise WorkError(r.stderr.strip())
    elif current_branch(project.root) != base:
        raise WorkError(f"이 폴더({project.root})가 {base} 브랜치가 아닙니다 — `git checkout {base}` 후 다시 실행하세요")
    if git_out(["status", "--porcelain", "--untracked-files=no"], project.root):
        raise WorkError(f"{project.root}에 커밋 안 된 변경이 있습니다")
    folder = project.find_work(wid)
    title = work_name_of(folder) if folder else ""
    r = git(
        ["merge", "--no-ff", name, "-m", f"merge: {wid} {title} [{wid}]".replace("  ", " ")], project.root, env={"LANTERN_SKIP_HOOKS": "1"}
    )
    if r.returncode != 0:
        git(["merge", "--abort"], project.root)
        raise WorkError(f"머지 충돌 — 직접 해결하세요:\n{r.stdout}{r.stderr}")
    msgs.append(f"✔ {name} → {base} 머지")
    if not keep:
        if wt and not in_place:
            # only the .env* copies made by `work start` may be thrown away with the folder
            stray = [
                l[3:]
                for l in git_out(["status", "--porcelain", "--untracked-files=all"], wt.path).splitlines()
                if l.startswith("??") and not Path(l[3:].strip('"')).name.startswith(".env")
            ]
            if stray:
                msgs.append(f"⚠ worktree에 커밋 안 된 새 파일이 있어 남겨 둡니다: {', '.join(stray[:3])} — 정리 후 git worktree remove")
                return msgs
            r = git(["worktree", "remove", "--force", str(wt.path)], project.root)
            if r.returncode != 0:
                msgs.append(f"⚠ worktree를 정리하지 못했습니다: {r.stderr.strip()}")
                return msgs
            msgs.append(f"✔ worktree 정리: {wt.path}")
        r = git(["branch", "-d", name], project.root)
        msgs.append(f"✔ 브랜치 삭제: {name}" if r.returncode == 0 else f"⚠ 브랜치를 지우지 못했습니다: {r.stderr.strip()}")
    msgs.append("다음: 현재 상태 반영 요약 → 승인 → 반영 → lantern work archive " + wid)
    return msgs


# --------------------------------------------------------------------------- archive


def archive(project: Project, work_id: str) -> Path:
    """Mark a work done and move its folder to the archive, fixing links that pointed into it.

    Args:
        project: The project.
        work_id: A work in progress, e.g. "W-012".

    Returns:
        The folder's new place.

    Raises:
        WorkError: The work is not in progress.

    Example:
        >>> archive(project, "W-012").parent.name  # doctest: +SKIP
        '보관'
    """
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise WorkError(f"진행 중인 작업 {work_id}가 없습니다")
    for doc in ("기획.md", "설계.md", "할 일.md", "기록.md"):
        p = folder / doc
        if p.exists():
            write(p, frontmatter.set_fields(read(p), {"status": project.enums.value("work_status", "done")}))
    dest_parent = project.folder("archive")
    dest_parent.mkdir(parents=True, exist_ok=True)
    dest = dest_parent / folder.name
    old_rel = project.docs_rel(folder)
    new_rel = project.docs_rel(dest_parent) + "/" + nfc(folder.name)
    shutil.move(str(folder), str(dest))
    rewrite_links(project, old_rel, new_rel)
    return dest


def rewrite_links(project: Project, old_rel: str, new_rel: str) -> list[Path]:
    """Rewrite `[[old_rel/…]]` and `](old_rel/…)` links after a folder moved (Obsidian is not watching our moves).

    Args:
        project: The project.
        old_rel: The folder's old path from the documents root.
        new_rel: Its new path from the documents root.

    Returns:
        The documents that were changed.

    Example:
        >>> rewrite_links(project, "2. 작업/W-012 로그인", "2. 작업/보관/W-012 로그인")  # doctest: +SKIP
        [PosixPath('…/개발문서 MOC.md')]
    """
    changed = []
    pat = re.compile(r"(\[\[)" + re.escape(old_rel) + r"(/)")
    pat_md = re.compile(r"(\]\()" + re.escape(old_rel.replace(" ", "%20")) + r"(/)")
    for p in project.docs.rglob("*.md"):
        text = read(p)
        new = pat.sub(lambda m: m.group(1) + new_rel + m.group(2), text)
        new = pat_md.sub(lambda m: m.group(1) + new_rel.replace(" ", "%20") + m.group(2), new)
        if new != text:
            write(p, new)
            changed.append(p)
    return changed
