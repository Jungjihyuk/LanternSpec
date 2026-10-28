"""git hooks — block structural mistakes, warn about content mistakes.

commit-msg  message    is there a task ID · are several tasks mixed in one commit
pre-commit  structure  docs/.git · .gitignore · .ignore · docs/ mixed into a code commit   (always blocks)
            schema     is a schema change recorded
            docs       lantern check on the changed documents
pre-push    docs-local block pushing the docs-local branch (only an allowed personal remote passes)

Content checks warn or block according to `git.hooks`. Shell shims call `lantern hook git-…`;
an existing non-LanternSpec hook is kept as `<name>.local` and still runs first.
"""

from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path

from ..core.project import Project, git_out, nfc

MARK = "# lanternspec hook"
HOOKS = {"commit-msg": "git-commit-msg", "pre-commit": "git-pre-commit", "pre-push": "git-pre-push"}
DOCS_BRANCH = "docs-local"
ID_RE = re.compile(r"\b(?:IDEA|W|ADR|D)-\d{3,}(?:-T\d{2,})?\b")
TASK_RE = re.compile(r"\bW-\d{3,}-T\d{2,}\b")
SKIP_MSG = re.compile(r"^(Merge |Revert |fixup! |squash! |amend! )|\[lantern\]")

SHIM = """#!/bin/sh
{mark} — `lantern hooks uninstall`로 지운다. 고치지 말 것.
HOOK_DIR=$(cd "$(dirname "$0")" && pwd)
{prelude}if [ -x "$HOOK_DIR/{name}.local" ]; then
  {local_call} || exit $?
fi
if command -v lantern >/dev/null 2>&1; then
  {feed}lantern hook {handler} "$@"
  exit $?
elif python3 -c "import lanternspec" >/dev/null 2>&1; then
  {feed}python3 -m lanternspec hook {handler} "$@"
  exit $?
fi
echo "lanternspec: lantern 명령을 찾지 못해 검사를 건너뜁니다" >&2
exit 0
"""


def hooks_dir(project: Project) -> Path:
    """Return the folder git runs hooks from (core.hooksPath, else the common `.git/hooks`).

    Args:
        project: The project.

    Returns:
        The hooks folder.

    Raises:
        RuntimeError: The project is not a git repository.

    Example:
        >>> hooks_dir(project).name  # doctest: +SKIP
        'hooks'
    """
    custom = git_out(["config", "--get", "core.hooksPath"], project.root)
    if custom:
        p = Path(custom)
        return p if p.is_absolute() else project.root / p
    common = git_out(["rev-parse", "--path-format=absolute", "--git-common-dir"], project.root)
    if not common:
        raise RuntimeError("git 저장소가 아닙니다")
    return Path(common) / "hooks"


def _shim(name: str) -> str:
    if name == "pre-push":  # stdin must reach both the local hook and ours
        return SHIM.format(
            mark=MARK,
            name=name,
            handler=HOOKS[name],
            prelude="INPUT=$(cat)\n",
            local_call=f'printf "%s\\n" "$INPUT" | "$HOOK_DIR/{name}.local" "$@"',
            feed='printf "%s\\n" "$INPUT" | ',
        )
    return SHIM.format(mark=MARK, name=name, handler=HOOKS[name], prelude="", local_call=f'"$HOOK_DIR/{name}.local" "$@"', feed="")


def install(project: Project) -> list[str]:
    """Install the hook shims, keeping any existing hook as `<name>.local`.

    Args:
        project: The project.

    Returns:
        Messages describing what was installed or kept.

    Raises:
        RuntimeError: The project is not a git repository.

    Example:
        >>> install(project)[-1]  # doctest: +SKIP
        '✔ git hook 설치: commit-msg, pre-commit, pre-push (…/.git/hooks)'
    """
    d = hooks_dir(project)
    d.mkdir(parents=True, exist_ok=True)
    msgs = []
    for name in HOOKS:
        p = d / name
        if p.exists() and MARK not in p.read_text(encoding="utf-8", errors="replace"):
            local = d / f"{name}.local"
            if not local.exists():
                p.rename(local)
                msgs.append(f"• 기존 {name} hook을 {name}.local로 보존 (먼저 실행됨)")
        p.write_text(_shim(name), encoding="utf-8")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    msgs.append(f"✔ git hook 설치: {', '.join(HOOKS)} ({d})")
    return msgs


def uninstall(project: Project) -> list[str]:
    """Remove our hook shims and put back any `<name>.local` hooks.

    Args:
        project: The project.

    Returns:
        Messages describing what was removed.

    Raises:
        RuntimeError: The project is not a git repository.

    Example:
        >>> uninstall(project)  # doctest: +SKIP
        ['✔ commit-msg 제거', '✔ pre-commit 제거', '✔ pre-push 제거']
    """
    d = hooks_dir(project)
    msgs = []
    for name in HOOKS:
        p = d / name
        if p.exists() and MARK in p.read_text(encoding="utf-8", errors="replace"):
            p.unlink()
            local = d / f"{name}.local"
            if local.exists():
                local.rename(p)
                msgs.append(f"• {name}.local을 원래 이름으로 되돌림")
            msgs.append(f"✔ {name} 제거")
    return msgs or ["설치된 LanternSpec hook이 없습니다"]


def status(project: Project) -> list[tuple[str, bool]]:
    """Tell which of our hooks are installed.

    Args:
        project: The project.

    Returns:
        (hook name, installed) for each hook; all False outside git.

    Example:
        >>> status(project)  # doctest: +SKIP
        [('commit-msg', True), ('pre-commit', True), ('pre-push', True)]
    """
    try:
        d = hooks_dir(project)
    except RuntimeError:
        return [(n, False) for n in HOOKS]
    return [(n, (d / n).exists() and MARK in (d / n).read_text(encoding="utf-8", errors="replace")) for n in HOOKS]


# --------------------------------------------------------------------------- handlers


def _skip() -> bool:
    return os.environ.get("LANTERN_SKIP_HOOKS") == "1"


def _mode(project: Project) -> str:
    return str(project.profile.get("git.hooks") or "warn")


def _say(lines: list[str]) -> None:
    for line in lines:
        print(line, file=sys.stderr)


def _toplevel() -> Path:
    return Path(git_out(["rev-parse", "--show-toplevel"], Path.cwd()) or Path.cwd())


def _branch(cwd: Path) -> str:
    b = git_out(["symbolic-ref", "--short", "-q", "HEAD"], cwd)
    return b or git_out(["rev-parse", "--abbrev-ref", "HEAD"], cwd)


def _staged(cwd: Path) -> list[str]:
    out = git_out(["diff", "--cached", "--name-only", "--diff-filter=ACMRD"], cwd)
    return [nfc(x) for x in out.splitlines() if x.strip()]


def _content_result(project: Project, problems: list[str], label: str) -> int:
    if not problems:
        return 0
    block = _mode(project) == "block"
    _say([f"{'✖' if block else '⚠'} LanternSpec {label}"] + [f"   {p}" for p in problems])
    if block:
        _say(["   (git.hooks: block — 고친 뒤 다시 커밋. 급하면 git commit --no-verify)"])
        return 1
    _say(["   (경고만 — 커밋은 진행됩니다. 막으려면 lantern.yaml git.hooks: block)"])
    return 0


def commit_msg(project: Project, msg_file: str) -> int:
    """Check a commit message: code commits need a task ID, and one commit should hold one task.

    Args:
        project: The project.
        msg_file: The file git passes with the message.

    Returns:
        The hook's exit code: 1 blocks the commit (only under `git.hooks: block`), 0 lets it through.

    Example:
        >>> commit_msg(project, ".git/COMMIT_EDITMSG")  # doctest: +SKIP
        0
    """
    if _skip():
        return 0
    text = Path(msg_file).read_text(encoding="utf-8", errors="replace")
    msg = "\n".join(l for l in text.split("\n") if not l.startswith("#")).strip()
    if not msg or SKIP_MSG.search(msg):
        return 0
    top = _toplevel()
    branch = _branch(top)
    docs_branch = branch == DOCS_BRANCH
    staged = _staged(top)
    from ..report.scan import is_doc_path

    code = staged if docs_branch else [f for f in staged if not is_doc_path(project, f)]
    problems: list[str] = []
    if code and not ID_RE.search(msg):
        where = "문서 브랜치" if docs_branch else "코드 커밋"
        problems.append(f"커밋 메시지: {where} 메시지에 할 일 번호가 없습니다 — 끝에 [W-001-T02] 처럼 붙이세요")
    tasks = sorted(set(TASK_RE.findall(msg)))
    if len(tasks) > 1:
        problems.append(f"커밋 메시지: 할 일 여러 개가 한 커밋에 섞였습니다 ({', '.join(tasks)}) — 할 일 하나 = 커밋 하나")
    return _content_result(project, problems, "커밋 메시지 검사")


def structure_problems(project: Project, cwd: Path | None = None, staged: list[str] | None = None) -> list[str]:
    """Check the docs storage structure (always blocking). Also used by `lantern doctor`.

    shared: no `docs/.git`, and .gitignore must not ignore docs/.
    local: `docs/` is the docs-local worktree, .gitignore ignores it, .ignore lets AI search find it again,
    and code commits carry no docs/ files.

    Args:
        project: The project.
        cwd: Where to read the current branch; the project root when None.
        staged: Staged files, to catch docs/ mixed into a code commit; not checked when None.

    Returns:
        The problems; empty when the structure is right.

    Example:
        >>> structure_problems(project)  # doctest: +SKIP
        []
    """
    cwd = cwd or project.root
    branch = _branch(cwd)
    docs = project.docs
    pattern = project.profile.docs_root.rstrip("/") + "/"
    gi = project.root / ".gitignore"
    ig = project.root / ".ignore"
    gi_has = gi.exists() and any(
        l.strip() in (pattern, "/" + pattern, pattern.rstrip("/")) for l in gi.read_text(encoding="utf-8").split("\n")
    )
    ig_has = ig.exists() and any(l.strip() in ("!" + pattern, "!/" + pattern) for l in ig.read_text(encoding="utf-8").split("\n"))
    out: list[str] = []
    if project.profile.remote == "shared":
        if (docs / ".git").exists():
            out.append("docs/ 안에 .git이 있습니다 (shared 방식에서는 없어야 함) — lantern doctor")
        if gi_has:
            out.append(".gitignore가 docs/를 무시합니다 (shared 방식이면 지워야 함)")
    else:
        g = docs / ".git"
        if g.is_dir():
            out.append("docs/.git이 폴더입니다 — docs-local 브랜치를 가리키는 표지판 파일이어야 합니다 (lantern docs-mode)")
        elif not g.exists():
            out.append("docs/가 docs-local worktree가 아닙니다 — lantern docs-mode local 로 만드세요")
        if not gi_has:
            out.append(".gitignore에 docs/가 없습니다")
        if not ig_has:
            out.append(".ignore에 !docs/가 없습니다 — AI 검색이 문서를 못 찾습니다")
        if branch != DOCS_BRANCH and staged is not None:
            mixed = [f for f in staged if f.startswith(pattern)]
            if mixed:
                out.append(f"코드 커밋에 docs/ 파일이 섞였습니다: {', '.join(mixed[:3])} — 문서는 docs-local에 따로 커밋")
    return out


def pre_commit(project: Project) -> int:
    """Run the pre-commit checks: structure (always blocks), then schema record and document format.

    Args:
        project: The project.

    Returns:
        The hook's exit code: 1 blocks the commit, 0 lets it through.

    Example:
        >>> pre_commit(project)  # doctest: +SKIP
        0
    """
    if _skip():
        return 0
    top = _toplevel()
    branch = _branch(top)
    staged = _staged(top)
    docs_branch = branch == DOCS_BRANCH
    structural = structure_problems(project, cwd=top, staged=staged)
    if structural:
        _say(["✖ LanternSpec 구조 검사 — 커밋을 막았습니다 (구조 실수는 항상 막음)"] + [f"   {p}" for p in structural])
        return 1
    problems: list[str] = []
    # schema change without a record
    from ..report.scan import is_doc_path, schema_files

    n = project.names
    if not docs_branch and not n.is_unused("schema"):
        sfiles = schema_files(project, staged)
        if sfiles:
            if project.profile.remote == "shared":
                recorded = any(nfc(f).endswith(nfc(n.file("record"))) for f in staged)
            else:
                docs_status = git_out(["status", "--porcelain"], project.docs) if project.docs.exists() else ""
                recent = git_out(["log", "--since=1.day", "--name-only", "--format="], project.docs) if project.docs.exists() else ""
                recorded = nfc(n.file("record")) in nfc(docs_status) or nfc(n.file("record")) in nfc(recent)
            if not recorded:
                problems.append(
                    f"스키마 기록: 스키마 파일이 바뀌었는데 {n.file('record')} 변경이 없습니다: {', '.join(sfiles[:3])}"
                    f" — 작업 {n.file('record')} '## {n.title('schema')}'에 남기세요"
                )
    # lantern check on the documents in this commit
    from . import check_docs

    if docs_branch:
        doc_paths = [top / f for f in staged if f.endswith(".md")]
    else:
        doc_paths = [
            project.root / f
            for f in staged
            if f.endswith(".md") and is_doc_path(project, f) and f.startswith(project.profile.docs_root.rstrip("/") + "/")
        ]
    doc_paths = [p for p in doc_paths if p.exists()]
    if doc_paths:
        rep = check_docs.run(project, doc_paths)
        bad = [f for f in rep.findings if f.level == "error"]
        warn = [f for f in rep.findings if f.level == "warn"]
        for f in bad:
            problems.append(f"문서 양식: {f.path}: {f.message}")
        if warn and not bad:
            _say([f"⚠ LanternSpec 문서 양식 참고: {f.path}: {f.message}" for f in warn[:5]])
    return _content_result(project, problems, "커밋 전 검사")


def pre_push(project: Project, remote: str, url: str, stdin_text: str) -> int:
    """Refuse to push the docs-local branch, unless the remote is allowed (`lantern.allowDocsRemote`).

    Args:
        project: The project.
        remote: The remote's name.
        url: The remote's URL (not used; git passes it).
        stdin_text: The refs git sends on stdin, one "local_ref local_sha remote_ref remote_sha" per line.

    Returns:
        The hook's exit code: 1 blocks the push, 0 lets it through.

    Example:
        >>> pre_push(project, "origin", url, "refs/heads/docs-local abc refs/heads/docs-local 000")  # doctest: +SKIP
        1
    """
    if _skip():
        return 0
    allowed = git_out(["config", "--get-all", "lantern.allowDocsRemote"], project.root).split()
    for line in stdin_text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local_ref, remote_ref = parts[0], parts[2]
        if f"refs/heads/{DOCS_BRANCH}" in (local_ref, remote_ref):
            if remote in allowed:
                return 0
            _say(
                [
                    f"✖ LanternSpec: {DOCS_BRANCH} 브랜치는 원격({remote})에 올리지 않습니다 (docs.remote: local)",
                    f"   개인 원격을 허용하려면: git config --add lantern.allowDocsRemote {remote}",
                ]
            )
            return 1
    return 0
