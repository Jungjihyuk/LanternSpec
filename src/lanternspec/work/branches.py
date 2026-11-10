"""`lantern work` — one work = one branch, parallel worktrees, finish, archive.

Responsibilities:
    - the branch of a work (named by `git.branch`), in this folder or in its own worktree
    - link a work and its branch: a name that can't be worked out from the rule is kept in the plan's `branch`
    - one-off exceptions a person asks for (merge elsewhere · no work branch), kept in this repository's git config
    - recommend a branch flow from the project's state (for /l-init)
    - warn when parallel works say they will change the same tables or files
    - finish a work: test, merge into the base branch, clean up; archive its folder and fix links

Not here:
    - running the test command → report/scan.py (run_tests)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core import frontmatter
from ..core.messages import msg
from ..core.names import WORK_DOCS
from ..core.project import Project, git, git_out, nfc, read, work_id_of, work_name_of, write
from ..core.taskfile import parse_tasks

_COMPLEX_FLOW = re.compile(r"^(release/|hotfix/|develop$|staging$)")
_BLANK = re.compile(r"\{[A-Za-z_]+\}")
_WORK_IN_BRANCH = re.compile(r"(?<![A-Z0-9-])W-\d{3,}(?=$|[^0-9])")
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


@dataclass
class BranchFlow:
    """Which branch flows to offer a project, and which one to recommend.

    Attributes:
        recommended: The flow to recommend: "A" · "B" · "C" · "D".
        choices: The flows to offer, in order.
        default_branch: The branch that goes out.
        branches: The branches that were looked at.

    Example:
        >>> BranchFlow("A", ["A"], "main", ["main"]).recommended
        'A'
    """

    recommended: str
    choices: list[str]
    default_branch: str
    branches: list[str]


def recommend_flow(branches: list[str], has_remote: bool, team: str, origin: str) -> BranchFlow:
    """Choose the branch flow to recommend: the first rule that fits wins.

    A flow a project already follows comes first, then review for a team, then an existing `dev`.
    Flows B and C need a GitHub remote to open PRs on, and flow D needs a branch setup to keep.

    Args:
        branches: Branch names, without the remote's prefix.
        has_remote: Whether the project has a GitHub remote.
        team: `project.team`: "solo" or "team".
        origin: `project.origin`: "greenfield" or "brownfield".

    Returns:
        The recommendation and the flows to offer.

    Example:
        >>> recommend_flow(["main", "dev"], True, "solo", "greenfield").recommended
        'B'
        >>> recommend_flow(["main"], False, "team", "greenfield").choices
        ['A']
    """
    names = sorted({b for b in branches if b != "docs-local" and not b.startswith("work/")})
    choices = ["A"] + (["B", "C"] if has_remote else [])
    if origin != "greenfield" or len(names) > 1:
        choices.append("D")
    if any(_COMPLEX_FLOW.match(b) for b in names):
        recommended = "D"
    elif has_remote and team == "team":
        recommended = "C"
    elif has_remote and team == "solo" and "dev" in names:
        recommended = "B"
    else:
        recommended = "A"
    default = "master" if "master" in names and "main" not in names else "main"
    return BranchFlow(recommended, choices, default, names)


def suggest_flow(project: Project, team: str, origin: str) -> BranchFlow:
    """Read the repository's branches and remote, and recommend a branch flow.

    Args:
        project: The project.
        team: `project.team`: "solo" or "team".
        origin: `project.origin`: "greenfield" or "brownfield".

    Returns:
        The recommendation and the flows to offer.

    Example:
        >>> suggest_flow(project, "solo", "greenfield").recommended  # doctest: +SKIP
        'A'
    """
    local = git_out(["branch", "--format=%(refname:short)"], project.root).splitlines()
    remote = git_out(["branch", "-r", "--format=%(refname:short)"], project.root).splitlines()
    names = local + [b.split("/", 1)[1] for b in remote if "/" in b and not b.endswith("/HEAD")]
    return recommend_flow(names, "github.com" in git_out(["remote", "-v"], project.root), team, origin)


def fill_branch(rule: str, work_id: str) -> str:
    """Fill the work ID into a branch rule; other blanks stay for a person or the AI to choose.

    Args:
        rule: The rule (`git.branch`), e.g. "feature/{id}-{slug}".
        work_id: The work, e.g. "w-012".

    Returns:
        The rule with `{id}` filled in.

    Example:
        >>> fill_branch("feature/{id}-{slug}", "w-012")
        'feature/W-012-{slug}'
    """
    return rule.replace("{id}", work_id.upper())


def fits_rule(rule: str, work_id: str, name: str) -> bool:
    """Tell whether a branch name follows a branch rule.

    Args:
        rule: The rule (`git.branch`).
        work_id: The work, e.g. "W-012".
        name: The branch name.

    Returns:
        Whether the name has the rule's fixed parts, with something in every blank.

    Example:
        >>> fits_rule("feature/{ticket}-{slug}", "W-012", "feature/JS-15-login")
        True
        >>> fits_rule("feature/{ticket}-{slug}", "W-012", "fix/JS-15")
        False
    """
    parts = _BLANK.split(fill_branch(rule, work_id))
    return re.fullmatch(".+".join(re.escape(p) for p in parts), name) is not None


def _rule(project: Project) -> str:
    return str(project.profile.get("git.branch") or "work/{id}")


def _exception(project: Project, wid: str, key: str) -> str:
    # git config, not the plan: every worktree sees it at once, whichever branch holds the plan's latest version
    return git_out(["config", "--get", f"lantern.{wid}.{key}"], project.root)


def _usual_base(project: Project) -> str:
    return str(project.profile.get("git.base") or "main")


def merge_target(project: Project, work_id: str) -> str:
    """Return the branch a work merges into: the one a person chose for this work, else `git.base`.

    Args:
        project: The project.
        work_id: The work, e.g. "w-012".

    Returns:
        The branch name.

    Example:
        >>> merge_target(project, "w-012")  # doctest: +SKIP
        'dev'
    """
    wid = work_id.upper()
    return _exception(project, wid, "into") or _exception(project, wid, "here") or _usual_base(project)


def branch_name(project: Project, work_id: str) -> str | None:
    """Return the branch of a work: the one chosen for it, else the plan's, else its old `work/` branch, else what the rule gives.

    A name chosen with `--name` is read from git config too, because the plan holding it may not be merged yet.

    Args:
        project: The project.
        work_id: The work, e.g. "w-012".

    Returns:
        The branch name; None when the rule has blanks and no name was chosen yet.

    Example:
        >>> branch_name(project, "w-012")  # doctest: +SKIP
        'work/W-012'
    """
    wid = work_id.upper()
    kept = _exception(project, wid, "here") or _exception(project, wid, "branch")
    if kept:
        return kept
    folder = project.find_work(wid)
    plan = project.doc_path(folder, "plan") if folder else None
    if plan is not None and plan.exists():
        kept = frontmatter.as_str(frontmatter.parse(read(plan)).meta.get("branch"))
        if kept:
            return kept
    if _branch_exists(project, f"work/{wid}"):
        return f"work/{wid}"
    name = fill_branch(_rule(project), wid)
    return None if _BLANK.search(name) else name


def work_of_branch(project: Project, branch: str) -> str | None:
    """Find the work a branch belongs to: by the work ID in its name, else by the name kept in the plans.

    Args:
        project: The project.
        branch: The branch name.

    Returns:
        The work ID; None when the branch belongs to no work.

    Example:
        >>> work_of_branch(project, "feature/JS-15-login")  # doctest: +SKIP
        'W-012'
    """
    m = _WORK_IN_BRANCH.search(branch)
    if m:
        return m.group(0)
    for folder in project.work_dirs():
        wid = work_id_of(folder)
        if branch_name(project, wid) == branch:
            return wid
    return None


def check_branch_name(project: Project, work_id: str, name: str) -> None:
    """Refuse a branch name that breaks the rule (`git.branch`) or that git can't use.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        name: The branch name.

    Raises:
        WorkError: The name does not follow the rule or is not a valid branch name.

    Example:
        >>> check_branch_name(project, "W-012", "feature/JS-15-login")  # doctest: +SKIP
    """
    rule = _rule(project)
    if not fits_rule(rule, work_id, name):
        raise WorkError(msg("Branch {name} doesn't follow the rule {rule} (lantern.yaml git.branch)", name=name, rule=rule))
    if git(["check-ref-format", "--branch", name], project.root).returncode != 0:
        raise WorkError(msg("{name} can't be a branch name", name=name))


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
    base = _usual_base(project)
    if _branch_exists(project, base):
        return base
    return "HEAD"


def _keep_into(project: Project, wid: str, name: str, into: str) -> None:
    """Check a one-off merge target and keep it; a branch that already started elsewhere can't change its target."""
    if not _branch_exists(project, into):
        raise WorkError(msg("Branch {name} doesn't exist", name=into))
    if into == name:
        raise WorkError(msg("{wid} is on {name} already — to work there directly: lantern work branch {wid} --here", wid=wid, name=name))
    if _branch_exists(project, name) and _exception(project, wid, "into") != into:
        raise WorkError(
            msg(
                "{name} already started from another branch, so its commits would all go to {into} — "
                "to start over from {into}, delete it first: git branch -D {name}",
                name=name,
                into=into,
            )
        )
    _remember(project, wid, "into", into)


def _remember(project: Project, wid: str, key: str, value: str) -> None:
    r = git(["config", f"lantern.{wid}.{key}", value], project.root)
    if r.returncode != 0:  # going on would send the work to the usual branch without a word
        raise WorkError(
            msg("Couldn't keep this work's choice in git config — run this outside the AI tool's sandbox: {strip}", strip=r.stderr.strip())
        )


def _forget_exceptions(project: Project, wid: str) -> None:
    git(["config", "--remove-section", f"lantern.{wid}"], project.root)


def work_here(project: Project, work_id: str) -> str:
    """Work on the current branch directly, with no work branch, because a person asked for it.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".

    Returns:
        What happened, as a message.

    Raises:
        WorkError: HEAD is detached, this is another work's branch, or the work already has its own branch.

    Example:
        >>> work_here(project, "W-012")  # doctest: +SKIP
        '⚠ W-012 작업 브랜치 없이 main에 바로 커밋합니다'
    """
    wid = work_id.upper()
    here = current_branch(project.root)
    if not here or here == "HEAD":
        raise WorkError(msg("This folder isn't on a branch — run `git checkout <branch>` first"))
    owner = work_of_branch(project, here)
    if owner and owner != wid:
        raise WorkError(msg("{here} is the branch of {owner} — move to the branch to work on first", here=here, owner=owner))
    own = branch_name(project, wid)
    if own and own != here and _branch_exists(project, own):
        raise WorkError(msg("{wid} already has its branch {name} — continue there, or delete it first", wid=wid, name=own))
    _remember(project, wid, "here", here)
    return msg("⚠ {wid}: no work branch, so commits go straight to {here}", wid=wid, here=here)


def _behind_remote(project: Project, base: str) -> str | None:
    """Warn when the remote's base branch has commits this one doesn't; silent when it can't be asked."""
    if "origin" not in git_out(["remote"], project.root).split():
        return None
    env = {"GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": "ssh -oBatchMode=yes"}
    if git(["fetch", "-q", "origin", base], project.root, env=env).returncode != 0:
        return None
    count = git_out(["rev-list", "--count", f"{base}..origin/{base}"], project.root)
    if not count.isdigit() or int(count) == 0:
        return None
    return msg("⚠ origin/{base} has {count} commits this {base} doesn't — run `git pull` on {base} first", base=base, count=count)


def ensure_branch(project: Project, work_id: str, from_ref: str | None = None, name: str | None = None, into: str | None = None) -> str:
    """Switch this folder to the work's branch, creating it from the base branch when needed (/l-build W-012).

    A new branch is not made on top of another branch unless asked: that would carry the other
    branch's unfinished code along, and merge it together with this work.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        from_ref: Start a new branch from here instead of the base branch.
        name: Use this branch name and keep it in the plan; needed when the rule has blanks.
        into: Merge this work into this branch instead of the base branch, and start from it too.

    Returns:
        What happened, as a message.

    Raises:
        WorkError: No name can be worked out, the name breaks the rule, this folder is on another
            branch and from_ref is not given, the merge target can't be used, or git could not
            switch or create the branch.

    Example:
        >>> ensure_branch(project, "W-012")  # doctest: +SKIP
        'work/W-012 브랜치를 만들었습니다'
    """
    wid = work_id.upper()
    if name:
        check_branch_name(project, wid, name)
    target = name or branch_name(project, wid)
    if target is None:
        raise WorkError(
            msg(
                "The branch rule {rule} has blanks to fill — choose a name: `lantern work branch {wid} --name <name>`",
                rule=_rule(project),
                wid=wid,
            )
        )
    if into:
        _keep_into(project, wid, target, into)
    if current_branch(project.root) == target:
        result = msg("Already on branch {name}", name=target)
    elif _branch_exists(project, target):
        r = git(["checkout", target], project.root)
        if r.returncode != 0:
            raise WorkError(r.stderr.strip())
        result = msg("Switched to branch {name}", name=target)
    else:
        chosen = _exception(project, wid, "into")
        base = chosen or _base(project)
        here = current_branch(project.root)
        if from_ref is None and not chosen and base != "HEAD" and here != base:
            raise WorkError(
                msg(
                    "This folder is on {here}, not the base branch {base} — run `git checkout {base}`, "
                    "or to build on {here}, `lantern work branch {work_id} --from {here}`",
                    here=here,
                    base=base,
                    work_id=wid,
                )
            )
        r = git(["checkout", "-b", target, from_ref or base], project.root)
        if r.returncode != 0:
            raise WorkError(r.stderr.strip())
        result = msg("Created branch {name}", name=target)
        behind = _behind_remote(project, base) if base != "HEAD" else None
        if behind:
            result += "\n" + behind
    if name:
        folder = project.find_work(wid)
        plan = project.doc_path(folder, "plan") if folder else None
        if plan is not None and plan.exists():
            write(plan, frontmatter.set_fields(read(plan), {"branch": name}, touch=False))
        _remember(project, wid, "branch", name)
    return result + _other_target_note(project, wid)


def _other_target_note(project: Project, wid: str) -> str:
    target, usual = merge_target(project, wid), _usual_base(project)
    return "" if target == usual else "\n" + msg("⚠ {wid} merges into {target}, not the usual {usual}", wid=wid, target=target, usual=usual)


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
    name = branch_name(project, work_id)
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
    ids = list(dict.fromkeys([w.upper() for w in work_ids] + _running_works(project)))
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


def _running_works(project: Project) -> list[str]:
    """Works already open in their own worktrees."""
    return [wid for wt in worktrees(project) if (wid := work_of_branch(project, wt.branch))]


def needs_parallel_check(project: Project, work_ids: list[str]) -> bool:
    """Tell whether starting these works makes two or more run at once (counting the ones already running).

    Args:
        project: The project.
        work_ids: The works about to start.

    Returns:
        True when two or more works would run in parallel.

    Example:
        >>> needs_parallel_check(project, ["W-012", "W-013"])  # doctest: +SKIP
        True
    """
    return len(dict.fromkeys([w.upper() for w in work_ids] + _running_works(project))) >= 2


def _dependency_files() -> list[str]:
    """File names that hold a project's dependencies, from each language's conventions (globs left out)."""
    from ..core import principles

    names = [str(p).partition(":")[0] for lang in principles.language_names() for p in principles.conventions(lang)["detect"]]
    return list(dict.fromkeys(n for n in names if "*" not in n))


def _built(project: Project, wid: str) -> tuple[set[str], list[str]] | None:
    """Code files a work's branch changed and dependency lines it added, against its base; None before any commit."""
    name = branch_name(project, wid)
    if name is None or not _branch_exists(project, name):
        return None
    base = merge_target(project, wid)
    if name == base or git_out(["rev-list", "--count", f"{base}..{name}"], project.root) in ("", "0"):
        return None
    docs = project.profile.docs_root.rstrip("/") + "/"
    files = {f for f in git_out(["diff", "--name-only", f"{base}...{name}"], project.root).splitlines() if not f.startswith(docs)}
    specs = [f":(glob)**/{n}" for n in _dependency_files()]
    added, current = [], ""
    for line in git_out(["diff", "--unified=0", f"{base}...{name}", "--", *specs], project.root).splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and current and line[1:].strip():
            added.append(f"{current}: {line[1:].strip()}")
    return files, added


def overlap(project: Project, work_ids: list[str]) -> list[str]:
    """Show what works running together share: same tables or files, linked decisions, and what they built.

    Before the works start this reads their designs. Once a work's branch has commits, it also
    shows the code files works really changed in common and the dependencies each added, so
    /l-finish can spot the same job done two ways (two sign-in methods, two date libraries).

    Args:
        project: The project.
        work_ids: The works to check, e.g. ["W-012", "W-013"].

    Returns:
        Shared touch points from the designs (works already running included), each work's
        linked decision records, then files changed in common and new dependency lines.

    Example:
        >>> overlap(project, ["W-012", "W-013"])  # doctest: +SKIP
        ['⚠ W-012 · W-013가 같은 곳을 고칩니다: 테이블 users', 'W-012 결정 기록: ADR-003']
    """
    out = conflicts(project, work_ids) or [msg("No shared tables or files in the designs")]
    ids = list(dict.fromkeys([w.upper() for w in work_ids] + _running_works(project)))
    for wid in ids:
        folder = project.find_work(wid, include_archive=False)
        design = project.doc_path(folder, "design") if folder else None
        adrs = frontmatter.parse(read(design)).meta.get("adr") if design and design.exists() else None
        items = adrs if isinstance(adrs, list) else [adrs] if adrs else []
        out.append(msg("{wid} decision records: {items}", wid=wid, items=", ".join(map(str, items)) or msg("none")))
    built = {wid: b for wid in ids if (b := _built(project, wid))}
    for i, a in enumerate(built):
        for b in list(built)[i + 1 :]:
            common = built[a][0] & built[b][0]
            if common:
                out.append(msg("⚠ {a} · {b} changed the same files: {items}", a=a, b=b, items=", ".join(sorted(common))))
    for wid, (_, added) in built.items():
        if added:
            out.append(msg("{wid} new dependency lines:", wid=wid))
            out += [f"  + {line}" for line in added]
    return out


def _install(path: Path) -> str | None:
    for lock, cmd in LOCKFILES:
        if (path / lock).exists():
            r = subprocess.run(cmd, shell=True, cwd=str(path), capture_output=True, text=True)
            result = msg("done") if r.returncode == 0 else msg("failed (check it yourself)")
            return f"{cmd} → {result}"
    return None


def start(
    project: Project,
    work_ids: list[str],
    install: bool = True,
    parent: Path | None = None,
    into: str | None = None,
    skip_check: bool = False,
) -> list[str]:
    """Start works in parallel, each in its own worktree next to the project folder.

    Each worktree gets `.env*` files copied, the docs folder linked in local mode, and
    its dependencies installed from the lock file it has.

    Args:
        project: The project.
        work_ids: The works to start, e.g. ["W-012", "W-013"].
        install: Install dependencies in each new worktree.
        parent: Folder to put the worktrees in; the project's parent when None.
        into: Merge these works into this branch instead of the base branch, and start from it too.
        skip_check: Start even when two or more works would run at once without /l-parallel.

    Returns:
        Messages: conflict warnings, then one line per work with how to open it.

    Raises:
        WorkError: The repository has no commit, a work folder is missing, git failed, or
            two or more works would run at once and skip_check is off.

    Example:
        >>> start(project, ["W-012"], install=False)[0]  # doctest: +SKIP
        '• W-012: /Users/me/app-W-012 (work/W-012)'
    """
    if git(["rev-parse", "--verify", "HEAD"], project.root).returncode != 0:
        raise WorkError(msg("No commits yet, so a worktree can't be made — commit first"))
    if not skip_check and needs_parallel_check(project, work_ids):
        ids = " ".join(dict.fromkeys([w.upper() for w in work_ids] + _running_works(project)))
        raise WorkError(
            msg(
                "Two or more works would run at once. In your AI tool, check the decisions they share first: "
                "/l-parallel {ids}. To start without the check: --skip-check",
                ids=ids,
            )
        )
    from ..core import state
    from ..tools import resolve

    tools = resolve(state.load(project).get("tools") or ["claude"])
    msgs: list[str] = []
    msgs += conflicts(project, work_ids)
    parent = parent or project.root.parent
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
        name = branch_name(project, wid)
        if name is None:
            raise WorkError(
                msg(
                    "The branch rule {rule} has blanks to fill — choose a name: `lantern work branch {wid} --name <name>`",
                    rule=_rule(project),
                    wid=wid,
                )
            )
        if into:
            _keep_into(project, wid, name, into)
        base = _exception(project, wid, "into") or _base(project)
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
            _ignore_docs_link(project)
        elif not (path / docs_rel / project.docs_rel(folder)).exists():
            msgs.append(
                msg("⚠ {wid}: the work folder isn't committed yet, so it's not in the worktree — commit the documents first", wid=wid)
            )
        note = _install(path) if install else None
        msgs.append(f"• {wid}: {path} ({name})" + (f" · {note}" if note else "") + _other_target_note(project, wid))
        target = merge_target(project, wid)
        merge_folder = next((t.path for t in worktrees(project) if t.branch == target), worktrees(project)[0].path)
        for tool in tools:
            command = tool.worktree_command(path, wid, merge_folder)
            msgs.append(msg('    In a terminal: cd "{path}" && {command}', path=path, command=command))
    return msgs


def _is_generated(project: Project, rel: str) -> bool:
    """Tell whether a file is a document `lantern close` or `lantern report` rebuilds whole."""
    path = nfc(str(project.root / rel))
    whole = (
        project.moc,
        project.folder("reports") / project.names.file("report"),
        project.folder("debt") / project.names.file("debt_status"),
    )
    return path in {nfc(str(p)) for p in whole} or path.startswith(nfc(str(project.folder("past_reports"))) + "/")


def _take_base_side(work_path: Path, files: list[str]) -> bool:
    """Finish a merge of the base branch by taking its side of these files; False when that can't be done (e.g. it deleted one)."""
    env = {"LANTERN_SKIP_HOOKS": "1"}
    return (
        all(git(["checkout", "--theirs", "--", f], work_path).returncode == 0 for f in files)
        and git(["add", "--", *files], work_path).returncode == 0
        and git(["commit", "--no-edit"], work_path, env=env).returncode == 0
    )


def _ignore_docs_link(project: Project) -> None:
    """Keep the local-mode docs link in a worktree out of git, in the repository's own exclude file.

    `.gitignore` says `docs/`, which matches only a folder; the link is a file to git, so it
    would show as new and block `finish` from removing the worktree.
    """
    common = git_out(["rev-parse", "--path-format=absolute", "--git-common-dir"], project.root)
    if not common:
        return
    exclude = Path(common) / "info" / "exclude"
    line = "/" + project.profile.docs_root
    lines = read(exclude).splitlines() if exclude.exists() else []
    if line not in lines:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        write(exclude, "\n".join([*lines, line]) + "\n")


def _same_folder(a: Path, b: Path) -> bool:
    return a.resolve() == b.resolve()


def _task_counts(project: Project, wid: str, root: Path | None = None) -> tuple[int, int] | None:
    """(done, total) tasks of a work as its folder (or `root`) sees them; None without a task list."""
    base = Project(root=root, profile=project.profile) if root else project
    folder = base.find_work(wid, include_archive=False) if base.docs.exists() else None
    if folder is None:
        folder = project.find_work(wid, include_archive=False)
    if folder is None or not project.doc_path(folder, "tasks").exists():
        return None
    ts = parse_tasks(read(project.doc_path(folder, "tasks")), project.names)
    return sum(t.done for t in ts), len(ts)


def _progress(project: Project, wid: str, root: Path | None = None) -> str:
    counts = _task_counts(project, wid, root)
    if counts is None:
        return msg("no tasks")
    return msg("{sum}/{count} done", sum=counts[0], count=counts[1])


def parallel_work_here(project: Project) -> str | None:
    """Tell which work's parallel worktree this runs in, if any.

    Works in their own worktrees leave the shared wrap-up (current state, archive, report) to
    /l-finish in the base folder, so /l-build stops after its own work there.

    Args:
        project: The project, loaded from the folder this runs in.

    Returns:
        The work ID when this runs inside a work's worktree other than the main folder; None otherwise.

    Example:
        >>> parallel_work_here(project)  # doctest: +SKIP
        'W-012'
    """
    trees = worktrees(project)
    if not trees or _same_folder(trees[0].path, project.root):
        return None
    here = next((t for t in trees if _same_folder(t.path, project.root)), None)
    return work_of_branch(project, here.branch) if here else None


def _target_of(project: Project, wid: str) -> str:
    target = merge_target(project, wid)
    return "" if target == _usual_base(project) else f"  → {target}"


def list_works(project: Project) -> list[str]:
    """List the works running on their own branches, with progress and uncommitted changes.

    A worktree whose tasks are all done is marked as waiting for /l-finish, one whose work the main
    folder already archived is marked for removal, and a branch left without a worktree that is
    already merged into its target is marked for deletion. A done work whose archiving waits
    (`archive_waits_for`) is listed with what it waits for.

    Args:
        project: The project.

    Returns:
        One line per work branch; a single "none" line when there are none.

    Example:
        >>> list_works(project)  # doctest: +SKIP
        ['W-012  work/W-012  /Users/me/app-W-012  3/3 완료  · /l-finish 대기']
    """
    out = []
    trees = worktrees(project)
    main = Project(root=trees[0].path, profile=project.profile) if trees else project
    for wt in trees:
        wid = work_of_branch(project, wt.branch)
        if wid is None:
            continue
        dirty = bool(git_out(["status", "--porcelain", "--untracked-files=no"], wt.path))
        note = msg("  (uncommitted changes)") if dirty else ""
        counts = _task_counts(project, wid, wt.path)
        own = not _same_folder(wt.path, trees[0].path)
        if own and main.find_work(wid, include_archive=False) is None and main.find_work(wid):
            note += msg('  · already finished — commit or delete its leftover files, then: git worktree remove "{path}"', path=wt.path)
        elif counts and counts[1] and counts[0] == counts[1] and own:
            note += msg("  · waiting for /l-finish")
        out.append(f"{wid}  {wt.branch}  {wt.path}  {_progress(project, wid, wt.path)}{note}{_target_of(project, wid)}")
    running = {work_of_branch(project, wt.branch) for wt in trees}
    for b in git_out(["branch", "--list", "--format=%(refname:short)"], project.root).splitlines():
        wid = work_of_branch(project, b)
        running.add(wid)
        if wid and not any(wt.branch == b for wt in trees):
            target = merge_target(project, wid)
            merged = target != b and git(["merge-base", "--is-ancestor", b, target], project.root).returncode == 0
            out.append(
                msg("{wid}  {b}  (no worktree)  {progress}", wid=wid, b=b, progress=_progress(project, wid))
                + _target_of(project, wid)
                + (msg("  · merged into {target} — delete it with git branch -d {b}", target=target, b=b) if merged else "")
            )
    done = project.enums.value("work_status", "done")
    for folder in main.work_dirs():
        wid = work_id_of(folder)
        plan = main.doc_path(folder, "plan")
        if wid in running or not plan.exists() or frontmatter.parse(read(plan)).meta.get("status") != done:
            continue
        waits = archive_waits_for(main, wid)
        out.append(
            msg("{wid}  done · archived once {works} finish — now: lantern work archive {wid} --now", wid=wid, works=" · ".join(waits))
            if waits
            else msg("{wid}  done · waiting to be archived: lantern work archive {wid}", wid=wid)
        )
    return out or [msg("No parallel works in progress")]


def _catch_up_note(project: Project, target: str) -> list[str]:
    usual = _usual_base(project)
    if target == usual:
        return []
    return [msg("⚠ {usual} doesn't have this yet — merge {target} into {usual} too", usual=usual, target=target)]


def finish(project: Project, work_id: str, test: bool = True, keep: bool = False) -> list[str]:
    """Finish a work: bring in the base branch, run the tests, merge into the base branch, and clean up.

    The base branch here is `merge_target`: `git.base` unless a person chose another for this work.
    The merge happens in the folder where the base branch is open, wherever this runs from.
    A work done directly on that branch (`--here`) has nothing to merge, so only the tests run.
    Conflicts only in generated documents resolve themselves; any other conflict stops the merge.
    A worktree this runs from inside stays, because a session is working in it. So does one this
    session can't delete (an AI tool's sandbox), since git would stop halfway through removing it.
    With `git.pr: work` it stops before merging: the PR does that, and the branch stays.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        test: Run build.test first; a failure stops the merge.
        keep: Keep the worktree and the branch after merging.

    Returns:
        Messages describing each step, ending with what to do next.

    Raises:
        WorkError: The branch is missing, there are uncommitted changes, the tests failed,
            the base branch is missing or not open in any folder, or a merge conflicted (it is aborted).

    Example:
        >>> finish(project, "W-012", test=False)[0]  # doctest: +SKIP
        '✔ work/W-012 → main 머지'
    """
    wid = work_id.upper()
    name = branch_name(project, wid)
    if name is None or not _branch_exists(project, name):
        raise WorkError(msg("Branch {name} doesn't exist", name=name or fill_branch(_rule(project), wid)))
    base = merge_target(project, wid)
    if not _branch_exists(project, base):
        raise WorkError(msg("Base branch {base} doesn't exist (lantern.yaml git.base)", base=base))
    direct = name == base
    msgs: list[str] = []
    wt = work_worktree(project, wid)
    main_folder = worktrees(project)[0].path  # git lists the main folder first
    work_path = wt.path if wt else main_folder
    if git_out(["status", "--porcelain", "--untracked-files=no"], work_path):
        raise WorkError(msg("{work_path} has uncommitted changes — commit and run again", work_path=work_path))
    if wt is None:
        r = git(["checkout", name], main_folder)
        if r.returncode != 0:
            raise WorkError(r.stderr.strip())
    behind = _behind_remote(project, base)
    if behind:
        msgs.append(behind)
    # the tests below must see what the base branch will hold after the merge
    r = git(["merge", "--no-edit", base], work_path, env={"LANTERN_SKIP_HOOKS": "1"}) if not direct else None
    if r is not None and r.returncode != 0:
        conflicted = git_out(["diff", "--name-only", "--diff-filter=U"], work_path).splitlines()
        if not conflicted:  # not a conflict at all, e.g. the git folder can't be written
            raise WorkError(r.stderr.strip() or r.stdout.strip())
        if all(_is_generated(project, f) for f in conflicted) and _take_base_side(work_path, conflicted):
            msgs.append(
                msg(
                    "ℹ Took {base}'s side of generated documents, which the wrap-up rebuilds: {files}",
                    base=base,
                    files=" · ".join(conflicted),
                )
            )
        else:
            git(["merge", "--abort"], work_path)
            raise WorkError(
                msg(
                    "{name} conflicts with {base}: {files} — on {name}, run `git merge {base}`, resolve it, then run this again",
                    name=name,
                    base=base,
                    files=" · ".join(conflicted),
                )
            )
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
    next_step = msg("Next: summary of the current-state update → approval → update → lantern work archive ") + wid
    if direct:
        _forget_exceptions(project, wid)
        msgs.append(msg("✔ The work is already on {base}, so there is nothing to merge", base=base))
        msgs.append(next_step)
        msgs.extend(_catch_up_note(project, base))
        return msgs
    pr = project.profile.get("git.pr")
    if pr == "work":
        msgs.append(
            msg(
                "✔ {name} is up to date with {base}. It merges through a PR: "
                "current-state update → lantern work archive {wid} → commit → /l-pr",
                name=name,
                base=base,
                wid=wid,
            )
        )
        return msgs
    into = next((t.path for t in worktrees(project) if t.branch == base), None)
    if into is None:
        if not _same_folder(work_path, main_folder):
            raise WorkError(
                msg("{base} isn't open in any folder — run `git checkout {base}` in {root} and try again", base=base, root=main_folder)
            )
        r = git(["checkout", base], main_folder)
        if r.returncode != 0:
            raise WorkError(r.stderr.strip())
        into = main_folder
    if git_out(["status", "--porcelain", "--untracked-files=no"], into):
        raise WorkError(msg("{root} has uncommitted changes", root=into))
    folder = project.find_work(wid)
    title = work_name_of(folder) if folder else ""
    r = git(["merge", "--no-ff", name, "-m", f"merge: {wid} {title} [{wid}]".replace("  ", " ")], into, env={"LANTERN_SKIP_HOOKS": "1"})
    if r.returncode != 0:
        git(["merge", "--abort"], into)
        raise WorkError(msg("Merge conflict — resolve it yourself:\n{stdout}{stderr}", stdout=r.stdout, stderr=r.stderr))
    msgs.append(msg("✔ Merged {name} → {base}", name=name, base=base))
    if not keep:
        own = wt if wt and not _same_folder(wt.path, main_folder) else None
        if own and _same_folder(own.path, project.root):
            msgs.append(
                msg(
                    "ℹ This session is inside {path}, so it stays. Do the next steps in {into}; "
                    'to clean up afterwards: cd "{into}" && lantern work finish {wid} --no-test',
                    path=own.path,
                    into=into,
                    wid=wid,
                )
            )
        elif own and not os.access(own.path.parent, os.W_OK):
            msgs.append(
                msg(
                    "ℹ This session can't delete {path}, so it stays. Don't run `git worktree remove` here: "
                    "it stops halfway and breaks the folder. A person cleans it up in a terminal: "
                    'cd "{into}" && lantern work finish {wid} --no-test',
                    path=own.path,
                    into=into,
                    wid=wid,
                )
            )
        else:
            if own:
                # only the .env* copies made by `work start` may be thrown away with the folder
                stray = [
                    l[3:]
                    for l in git_out(["status", "--porcelain", "--untracked-files=all"], own.path).splitlines()
                    if l.startswith("??")
                    and not Path(l[3:].strip('"')).name.startswith(".env")
                    and l[3:].strip('"').rstrip("/") != project.profile.docs_root  # the local-mode docs link
                ]
                if stray:
                    msgs.append(
                        msg(
                            "⚠ Keeping the worktree because it has new uncommitted files: {items} — clean up, then git worktree remove",
                            items=", ".join(stray[:3]),
                        )
                    )
                    return msgs
                r = git(["worktree", "remove", "--force", str(own.path)], into)
                if r.returncode != 0:
                    msgs.append(msg("⚠ Couldn't remove the worktree: {strip}", strip=r.stderr.strip()))
                    return msgs
                msgs.append(msg("✔ Removed worktree: {path}", path=own.path))
            r = git(["branch", "-d", name], into)
            if r.returncode == 0:
                _forget_exceptions(project, wid)
            msgs.append(
                msg("✔ Deleted branch: {name}", name=name)
                if r.returncode == 0
                else msg("⚠ Couldn't delete the branch: {strip}", strip=r.stderr.strip())
            )
    msgs.append(next_step)
    catch_up = _catch_up_note(project, base)
    msgs.extend(catch_up)
    if pr == "deploy" and not catch_up:
        deploy = project.profile.get("git.deploy")
        msgs.append(msg("To send it out later: /l-pr ({base} → {deploy})", base=base, deploy=deploy))
    return msgs


# --------------------------------------------------------------------------- archive


def archive_waits_for(project: Project, work_id: str) -> list[str]:
    """List the works running in other worktrees whose documents link into this work's folder.

    Archiving moves the folder and rewrites those links in this folder's copy of their documents,
    which the worktree is also editing. Waiting until they finish keeps their documents untouched.

    Args:
        project: The project, loaded from the base folder.
        work_id: The work to archive, e.g. "W-012".

    Returns:
        The IDs of the running works that link to it; empty when it can be archived now.

    Example:
        >>> archive_waits_for(project, "W-012")  # doctest: +SKIP
        ['W-013']
    """
    wid = work_id.upper()
    folder = project.find_work(wid, include_archive=False)
    trees = worktrees(project)
    if folder is None or not trees:
        return []
    patterns = _link_patterns(project.docs_rel(folder))
    waits = []
    for tree in trees[1:]:  # git lists the main folder first
        other_id = work_of_branch(project, tree.branch)
        other = project.find_work(other_id, include_archive=False) if other_id and other_id != wid else None
        if other and any(pat.search(read(doc)) for doc in other.rglob("*.md") for pat in patterns):
            waits.append(other_id)
    return waits


def archive(project: Project, work_id: str, now: bool = False) -> list[str]:
    """Mark a work done and move its folder to the archive, fixing links that pointed into it.

    While a work running in another worktree links to it, the folder only gets marked done and
    stays: it is archived with that work's /l-finish, or with `now` (rewriting that work's links here).

    Args:
        project: The project.
        work_id: A work in progress, e.g. "W-012".
        now: Archive even while running works link to it.

    Returns:
        Messages saying where the work went or why it waits.

    Raises:
        WorkError: The work is not in progress.

    Example:
        >>> archive(project, "W-012")  # doctest: +SKIP
        ['✔ 보관: docs/2. 작업/보관/W-012 로그인']
    """
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise WorkError(msg("No work in progress {work_id}", work_id=work_id))
    for role in WORK_DOCS:
        p = project.doc_path(folder, role)
        if p.exists():
            write(p, frontmatter.set_fields(read(p), {"status": project.enums.value("work_status", "done")}))
    waits = [] if now else archive_waits_for(project, work_id)
    if waits:
        return [
            msg(
                "⏸ {wid} stays until {works} finish, since their documents link to it — "
                "the next /l-finish archives it, or now: lantern work archive {wid} --now",
                wid=work_id.upper(),
                works=" · ".join(waits),
            )
        ]
    dest_parent = project.folder("archive")
    dest_parent.mkdir(parents=True, exist_ok=True)
    dest = dest_parent / folder.name
    old_rel = project.docs_rel(folder)
    new_rel = project.docs_rel(dest_parent) + "/" + nfc(folder.name)
    shutil.move(str(folder), str(dest))
    rewrite_links(project, old_rel, new_rel)
    return [msg("✔ Archived: {rel}", rel=project.rel(dest))]


def _link_patterns(old_rel: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    """Wikilink and Markdown link patterns pointing into a folder."""
    return (
        re.compile(r"(\[\[)" + re.escape(old_rel) + r"(/)"),
        re.compile(r"(\]\()" + re.escape(old_rel.replace(" ", "%20")) + r"(/)"),
    )


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
    pat, pat_md = _link_patterns(old_rel)
    for p in project.docs.rglob("*.md"):
        text = read(p)
        new = pat.sub(lambda m: m.group(1) + new_rel + m.group(2), text)
        new = pat_md.sub(lambda m: m.group(1) + new_rel.replace(" ", "%20") + m.group(2), new)
        if new != text:
            write(p, new)
            changed.append(p)
    return changed
