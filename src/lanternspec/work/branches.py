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
from ..core.messages import msg
from ..core.names import WORK_DOCS
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
        return msg("Already on branch {name}", name=name)
    if _branch_exists(project, name):
        r = git(["checkout", name], project.root)
        if r.returncode != 0:
            raise WorkError(r.stderr.strip())
        return msg("Switched to branch {name}", name=name)
    r = git(["checkout", "-b", name], project.root)
    if r.returncode != 0:
        raise WorkError(r.stderr.strip())
    return msg("Created branch {name}", name=name)


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
    design = project.doc_path(folder, "design") if folder else None
    if design is None or not design.exists():
        return set()
    text = frontmatter.parse(read(design)).body
    points: set[str] = set()
    for block in re.findall(r"```dbml\n(.*?)```", text, re.S):
        points |= {msg("table {m}", m=m) for m in re.findall(r"(?im)^\s*Table\s+\"?([\w.]+)\"?", block)}
    for m in re.findall(r"`([\w./\-]+\.[A-Za-z0-9]{1,6})`", text):
        if "/" in m and not m.startswith(project.names.folder("screens") + "/"):
            points.add(msg("file {m}", m=m))
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
                warnings.append(msg("⚠ {a} · {b} change the same places: {items}", a=a, b=b, items=", ".join(sorted(common))))
    return warnings


def _install(path: Path) -> str | None:
    for lock, cmd in LOCKFILES:
        if (path / lock).exists():
            r = subprocess.run(cmd, shell=True, cwd=str(path), capture_output=True, text=True)
            result = msg("done") if r.returncode == 0 else msg("failed (check it yourself)")
            return f"{cmd} → {result}"
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
        raise WorkError(msg("No commits yet, so a worktree can't be made — commit first"))
    msgs: list[str] = []
    msgs += conflicts(project, work_ids)
    parent = parent or project.root.parent
    base = _base(project)
    for wid in work_ids:
        wid = wid.upper()
        folder = project.find_work(wid, include_archive=False)
        if folder is None:
            raise WorkError(msg("No folder for work {wid} — run /l-plan first", wid=wid))
        existing = work_worktree(project, wid)
        if existing:
            msgs.append(msg("• {wid}: already in progress at {path}", wid=wid, path=existing.path))
            continue
        path = parent / f"{project.root.name}-{wid}"
        name = branch_name(wid)
        args = ["worktree", "add", str(path), name] if _branch_exists(project, name) else ["worktree", "add", "-b", name, str(path), base]
        r = git(args, project.root)
        if r.returncode != 0:
            raise WorkError(msg("{wid}: couldn't create the worktree — {strip}", wid=wid, strip=r.stderr.strip()))
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
            msgs.append(
                msg("⚠ {wid}: the work folder isn't committed yet, so it's not in the worktree — commit the documents first", wid=wid)
            )
        note = _install(path) if install else None
        msgs.append(f"• {wid}: {path} ({name})" + (f" · {note}" if note else ""))
        msgs.append(msg('    In a terminal: cd "{path}" && claude "/l-build {wid}"', path=path, wid=wid))
    return msgs


def _progress(project: Project, wid: str, root: Path | None = None) -> str:
    base = Project(root=root, profile=project.profile) if root else project
    folder = base.find_work(wid, include_archive=False) if base.docs.exists() else None
    if folder is None:
        folder = project.find_work(wid, include_archive=False)
    if folder is None or not project.doc_path(folder, "tasks").exists():
        return msg("no tasks")
    ts = parse_tasks(read(project.doc_path(folder, "tasks")), project.names)
    return msg("{sum}/{count} done", sum=sum(t.done for t in ts), count=len(ts))


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
        note = msg("  (uncommitted changes)") if dirty else ""
        out.append(f"{wid}  {wt.branch}  {wt.path}  {_progress(project, wid, wt.path)}{note}")
    for b in git_out(["branch", "--list", "work/*", "--format=%(refname:short)"], project.root).splitlines():
        if not any(wt.branch == b for wt in worktrees(project)):
            wid = b.split("/", 1)[1]
            out.append(msg("{wid}  {b}  (no worktree)  {progress}", wid=wid, b=b, progress=_progress(project, wid)))
    return out or [msg("No parallel works in progress")]


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
        raise WorkError(msg("Branch {name} doesn't exist", name=name))
    msgs: list[str] = []
    wt = work_worktree(project, wid)
    in_place = wt is not None and wt.path.resolve() == project.root.resolve()
    work_path = wt.path if wt else project.root
    if git_out(["status", "--porcelain", "--untracked-files=no"], work_path):
        raise WorkError(msg("{work_path} has uncommitted changes — commit and run again", work_path=work_path))
    if test:
        cmd = project.profile.get("build.test")
        if cmd:
            from ..report.scan import run_tests

            res = run_tests(project, str(cmd), cwd=work_path)
            if not res["ok"]:
                raise WorkError(msg("Tests failed — not merging (`{cmd}`)\n{tail}", cmd=cmd, tail=res["tail"]))
            msgs.append(msg("✔ Tests passed (`{cmd}`)", cmd=cmd))
        else:
            msgs.append(msg("ℹ No build.test, so tests were skipped"))
    base = str(project.profile.get("git.base") or "main")
    if not _branch_exists(project, base):
        raise WorkError(msg("Base branch {base} doesn't exist (lantern.yaml git.base)", base=base))
    if in_place:
        r = git(["checkout", base], project.root)
        if r.returncode != 0:
            raise WorkError(r.stderr.strip())
    elif current_branch(project.root) != base:
        raise WorkError(
            msg("This folder ({root}) is not on branch {base} — run `git checkout {base}` and try again", root=project.root, base=base)
        )
    if git_out(["status", "--porcelain", "--untracked-files=no"], project.root):
        raise WorkError(msg("{root} has uncommitted changes", root=project.root))
    folder = project.find_work(wid)
    title = work_name_of(folder) if folder else ""
    r = git(
        ["merge", "--no-ff", name, "-m", f"merge: {wid} {title} [{wid}]".replace("  ", " ")], project.root, env={"LANTERN_SKIP_HOOKS": "1"}
    )
    if r.returncode != 0:
        git(["merge", "--abort"], project.root)
        raise WorkError(msg("Merge conflict — resolve it yourself:\n{stdout}{stderr}", stdout=r.stdout, stderr=r.stderr))
    msgs.append(msg("✔ Merged {name} → {base}", name=name, base=base))
    if not keep:
        if wt and not in_place:
            # only the .env* copies made by `work start` may be thrown away with the folder
            stray = [
                l[3:]
                for l in git_out(["status", "--porcelain", "--untracked-files=all"], wt.path).splitlines()
                if l.startswith("??") and not Path(l[3:].strip('"')).name.startswith(".env")
            ]
            if stray:
                msgs.append(
                    msg(
                        "⚠ Keeping the worktree because it has new uncommitted files: {items} — clean up, then git worktree remove",
                        items=", ".join(stray[:3]),
                    )
                )
                return msgs
            r = git(["worktree", "remove", "--force", str(wt.path)], project.root)
            if r.returncode != 0:
                msgs.append(msg("⚠ Couldn't remove the worktree: {strip}", strip=r.stderr.strip()))
                return msgs
            msgs.append(msg("✔ Removed worktree: {path}", path=wt.path))
        r = git(["branch", "-d", name], project.root)
        msgs.append(
            msg("✔ Deleted branch: {name}", name=name)
            if r.returncode == 0
            else msg("⚠ Couldn't delete the branch: {strip}", strip=r.stderr.strip())
        )
    msgs.append(msg("Next: summary of the current-state update → approval → update → lantern work archive ") + wid)
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
        raise WorkError(msg("No work in progress {work_id}", work_id=work_id))
    for role in WORK_DOCS:
        p = project.doc_path(folder, role)
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
