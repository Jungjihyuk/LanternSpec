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

from ..core.messages import msg
from ..core.project import Project, git_out, nfc

MARK = "# lanternspec hook"
HOOKS = {"commit-msg": "git-commit-msg", "pre-commit": "git-pre-commit", "pre-push": "git-pre-push"}
DOCS_BRANCH = "docs-local"
ID_RE = re.compile(r"\b(?:IDEA|W|ADR|D)-\d{3,}(?:-T\d{2,})?\b")
TASK_RE = re.compile(r"\bW-\d{3,}-T\d{2,}\b")
SKIP_MSG = re.compile(r"^(Merge |Revert |fixup! |squash! |amend! )|\[lantern\]")

SHIM = """#!/bin/sh
{mark} — {remove_note}
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
echo "lanternspec: {not_found}" >&2
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
        raise RuntimeError(msg("Not a git repository"))
    return Path(common) / "hooks"


def _shim(name: str) -> str:
    text = {
        "remove_note": msg("remove with `lantern hooks uninstall`. Don't edit."),
        "not_found": msg("lantern command not found, so the check is skipped"),
    }
    if name == "pre-push":  # stdin must reach both the local hook and ours
        return SHIM.format(
            **text,
            mark=MARK,
            name=name,
            handler=HOOKS[name],
            prelude="INPUT=$(cat)\n",
            local_call=f'printf "%s\\n" "$INPUT" | "$HOOK_DIR/{name}.local" "$@"',
            feed='printf "%s\\n" "$INPUT" | ',
        )
    return SHIM.format(**text, mark=MARK, name=name, handler=HOOKS[name], prelude="", local_call=f'"$HOOK_DIR/{name}.local" "$@"', feed="")


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
                msgs.append(msg("• Kept the existing {name} hook as {name}.local (runs first)", name=name))
        p.write_text(_shim(name), encoding="utf-8")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    msgs.append(msg("✔ git hooks installed: {items} ({d})", items=", ".join(HOOKS), d=d))
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
                msgs.append(msg("• Restored {name}.local to its original name", name=name))
            msgs.append(msg("✔ Removed {name}", name=name))
    return msgs or [msg("No LanternSpec hooks installed")]


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
        _say([msg("   (git.hooks: block — fix it and commit again. In a hurry, git commit --no-verify)")])
        return 1
    _say([msg("   (warning only — the commit goes ahead. To block, lantern.yaml git.hooks: block)")])
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
    message = "\n".join(l for l in text.split("\n") if not l.startswith("#")).strip()
    if not message or SKIP_MSG.search(message):
        return 0
    top = _toplevel()
    branch = _branch(top)
    docs_branch = branch == DOCS_BRANCH
    staged = _staged(top)
    from ..report.scan import is_doc_path

    code = staged if docs_branch else [f for f in staged if not is_doc_path(project, f)]
    problems: list[str] = []
    if code and not ID_RE.search(message):
        where = msg("the docs branch") if docs_branch else msg("code commit")
        problems.append(msg("Commit message: the {where} message has no task ID — add one at the end, like [W-001-T02]", where=where))
    tasks = sorted(set(TASK_RE.findall(message)))
    if len(tasks) > 1:
        problems.append(msg("Commit message: several tasks in one commit ({items}) — one task = one commit", items=", ".join(tasks)))
    return _content_result(project, problems, msg("commit message check"))


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
            out.append(msg("docs/ has a .git (it shouldn't in the shared mode) — lantern doctor"))
        if gi_has:
            out.append(msg(".gitignore ignores docs/ (remove it in the shared mode)"))
    else:
        g = docs / ".git"
        if g.is_dir():
            out.append(msg("docs/.git is a folder — it must be a pointer file to the docs-local branch (lantern docs-mode)"))
        elif not g.exists():
            out.append(msg("docs/ is not the docs-local worktree — make it with lantern docs-mode local"))
        if not gi_has:
            out.append(msg(".gitignore doesn't have docs/"))
        if not ig_has:
            out.append(msg(".ignore doesn't have !docs/ — AI search can't find the documents"))
        if branch != DOCS_BRANCH and staged is not None:
            mixed = [f for f in staged if f.startswith(pattern)]
            if mixed:
                out.append(
                    msg(
                        "docs/ files are mixed into a code commit: {items} — commit documents separately in docs-local",
                        items=", ".join(mixed[:3]),
                    )
                )
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
        _say(
            [msg("✖ LanternSpec structure check — blocked the commit (structure mistakes are always blocked)")]
            + [f"   {p}" for p in structural]
        )
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
                    msg(
                        "Schema log: schema files changed but {file} didn't: {items} — record it under '## {title}' in the work's {file}",
                        file=n.file("record"),
                        items=", ".join(sfiles[:3]),
                        title=n.title("schema"),
                    )
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
            problems.append(msg("Document format: {path}: {message}", path=f.path, message=f.message))
        if warn and not bad:
            _say([msg("⚠ LanternSpec document format note: {path}: {message}", path=f.path, message=f.message) for f in warn[:5]])
    return _content_result(project, problems, msg("pre-commit check"))


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
                    msg(
                        "✖ LanternSpec: the {docs_branch} branch is not pushed to a remote ({remote}) (docs.remote: local)",
                        docs_branch=DOCS_BRANCH,
                        remote=remote,
                    ),
                    msg("   To allow a private remote: git config --add lantern.allowDocsRemote {remote}", remote=remote),
                ]
            )
            return 1
    return 0
