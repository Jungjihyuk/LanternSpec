"""Check and template commands: check · lint (code) · template · legacy · hooks (git) · doctor."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..core.messages import msg
from .common import Add, CliError, _p, _print


def cmd_check(a: argparse.Namespace) -> int:
    """`lantern check` — check document formats (all, changed, or given documents; `--epic` for acceptance criteria)."""
    from ..check import check_docs
    from ..work import epic_rules

    project = _p()
    if a.epic is not None:
        findings = epic_rules.run(project, a.epic or None)
        rep = check_docs.Report(findings, files=len({f.path for f in findings}) or 1)
    else:
        paths = None
        if a.changed:
            paths = check_docs.changed_docs(project)
        elif a.paths:
            paths = []
            for raw in a.paths:
                p = Path(raw)
                cands = [p, project.root / raw, project.docs / raw]
                found = next((c for c in cands if c.exists()), None)
                if found is None:
                    raise CliError(msg("Not found: {raw}", raw=raw))
                paths += sorted(found.rglob("*.md")) if found.is_dir() else [found]
        rep = check_docs.run(project, paths, templates=True)
    if a.json:
        print(rep.to_json())
    else:
        print(rep.format(show_info=not a.quiet))
    if rep.errors or (a.strict and rep.warnings):
        return 1
    return 0


def cmd_template(a: argparse.Namespace) -> int:
    """`lantern template …` — list, lint, version and migrate templates."""
    from ..check import templates as tc

    project = _p()
    if a.level_auto:
        a.level = "auto"
    if a.action == "list":
        _print(tc.list_rows(project) or [msg("No templates — lantern scaffold init")])
    elif a.action == "show":
        if not a.name:
            raise CliError(msg("lantern template show <name>"))
        print(tc.show(a.name, project.language))
    elif a.action == "lint":
        from ..check.check_docs import Report

        targets = [a.name] if a.name else tc.names(project)
        findings = [f for n in targets for f in tc.lint(project, n)]
        print(Report(findings, len(targets)).format())
        return 1 if any(f.level == "error" for f in findings) else 0
    elif a.action == "level":
        lvl, source = tc.level(project, a.name)
        print(msg("{name}: {value} (compared with: {source})", name=a.name, value=lvl or msg("no changes"), source=source))
    elif a.action == "bump":
        print("✔ " + tc.bump(project, a.name, a.level or "auto", a.note or msg("refined")))
    elif a.action == "outdated":
        rows = tc.outdated(project, a.name, include_inactive=a.all)
        if not rows:
            print(msg("No documents on an old template version"))
        for o in rows:
            hint = msg("→ suggest migrate") if o.gap == "major" else (msg("ℹ changed") if o.gap == "minor" else msg("unchanged"))
            print(f"{project.rel(o.path)}  {o.template} {o.have} → {o.current} ({o.gap}) {hint}{'' if o.active else msg(' · finished')}")
    elif a.action == "diff":
        print(tc.diff_base(project, a.name))
    elif a.action == "usage":
        _print(tc.usage(project, a.name))
    elif a.action == "new":
        if not a.source:
            raise CliError(msg("lantern template new <name> --from <draft file>"))
        text = tc.skeleton_from(project, a.name, Path(a.source))
        if a.apply:
            from ..core.project import write

            dest = project.templates_dir / f"{a.name}.md"
            if dest.exists():
                raise CliError(msg("Already exists: {rel}", rel=project.rel(dest)))
            write(dest, text)
            print(f'✔ {project.rel(dest)} — lantern template lint "{a.name}"')
        else:
            print(text)
            print(msg("\n(preview — once approved, --apply)"))
    elif a.action == "migrate":
        maps = {}
        for m in a.map or []:
            if "=" not in m:
                raise CliError(msg('--map "old section=new section"'))
            k, v = m.split("=", 1)
            maps[k.strip()] = v.strip()
        _print(tc.migrate(project, a.name, maps, a.apply, to=a.to, dest=a.dest))
    return 0


def cmd_legacy(a: argparse.Namespace) -> int:
    """`lantern legacy adopt|todos` — keep existing documents in `5. 기존 문서/`, or list their TODOs."""
    from ..check import legacy

    project = _p()
    if a.action == "adopt":
        moved = legacy.adopt(project, Path(a.source) if a.source else None)
        _print([f"✔ {m}" for m in moved] or [msg("No legacy documents to move")])
    else:
        rows = legacy.todos(project)
        if not rows:
            print(msg("No TODOs · later items in the legacy documents"))
        for r in rows:
            print(f"- {r['text'].lstrip('-*+ ').strip()}  ({r['file']}:{r['line']})")
    return 0


def cmd_hooks(a: argparse.Namespace) -> int:
    """`lantern hooks install|uninstall|status` — manage the git hooks."""
    from ..check import githooks

    project = _p()
    if a.action == "install":
        _print(githooks.install(project))
    elif a.action == "uninstall":
        _print(githooks.uninstall(project))
    else:
        for name, ok in githooks.status(project):
            print(f"{'✔' if ok else '·'} {name}")
    return 0


def cmd_doctor(a: argparse.Namespace) -> int:
    """`lantern doctor` — check that the project's structure matches lantern.yaml."""
    from ..check import doctor

    rows = doctor.run(_p())
    print(doctor.format_result(rows))
    return 1 if any(r[0] == doctor.BAD for r in rows) else 0


def cmd_lint(a: argparse.Namespace) -> int:
    """`lantern lint` — run the lint and type-check commands of each part, or build.lint and build.typecheck (/l-build · CI)."""
    from ..report.scan import run_tests
    from ..tools.parts import commands

    project = _p()
    cmds = [(role, part, cmd) for role in ("lint", "typecheck") for part, cmd in commands(project, role, ci=a.ci)]
    if not cmds:
        print(msg("ℹ No build.lint · build.typecheck, so skipped (lantern principles detect --write)"))
        return 0
    warn_only = a.ci and project.profile.ci_lint == "warn"
    failed = 0
    for role, part, cmd in cmds:
        res = run_tests(project, cmd, project.root / part if part else None)
        where = f"{part} · " if part else ""
        print(f"{'✔' if res['ok'] else '⚠' if warn_only else '✖'} {where}{role}: `{cmd}`")
        if not res["ok"]:
            failed += 1
            print(res["tail"])
            if warn_only:  # a passing step hides its log, so GitHub Actions shows this on the run's page
                print(f"::warning::{where}{role}: {cmd}")
    if warn_only and failed:
        print(
            msg(
                "⚠ {count} checks failed, but CI passes (build.ci_lint: warn) — once they are clean, set build.ci_lint: block", count=failed
            )
        )
        return 0
    return 1 if failed else 0


def cmd_check_pr(a: argparse.Namespace) -> int:
    """`lantern check-pr` — check a pull request's title and commits for work IDs (CI runs it)."""
    from ..check.pr_check import pr_problems

    project = _p()
    problems = pr_problems(project, a.title, a.range)
    if not problems:
        print(msg("✔ PR title and commits have work IDs"))
        return 0
    block = project.profile.get("git.hooks") == "block"
    for p in problems:
        print(f"{'✖' if block else '⚠'} {p}")
    if not block:
        print(msg("(warning only — to fail the check, lantern.yaml git.hooks: block)"))
    return 1 if block else 0


def register(add: Add) -> None:
    """Register the check and template commands."""
    p = add("check-pr", cmd_check_pr, msg("Check a pull request's title and commits for work IDs (for CI)"))
    p.add_argument("--title", required=True)
    p.add_argument("--range", required=True, help=msg("The PR's commits, like base..head"))
    p = add("check", cmd_check, msg("Check document formats"))
    p.add_argument("paths", nargs="*")
    p.add_argument("--changed", action="store_true")
    p.add_argument("--epic", nargs="?", const="", help=msg("Check acceptance-criteria rules [W-012]"))
    p.add_argument("--json", action="store_true")
    p.add_argument("--quiet", action="store_true", help=msg("Hide notes (ℹ)"))
    p.add_argument("--strict", action="store_true", help=msg("Treat warnings as failures"))
    p = add("lint", cmd_lint, msg("Code lint · type check (each part's commands, or lantern.yaml build.lint · build.typecheck)"))
    p.add_argument("--ci", action="store_true", help=msg("For CI: leave out parts with ci: false, and follow build.ci_lint"))
    p = add("template", cmd_template, msg("Templates: list · show · lint · level · bump · outdated · diff · usage · new · migrate"))
    p.add_argument("action", choices=["list", "show", "lint", "level", "bump", "outdated", "diff", "usage", "new", "migrate"])
    p.add_argument("name", nargs="?")
    p.add_argument("level", nargs="?", help="bump: patch|minor|major|auto")
    p.add_argument("--auto", dest="level_auto", action="store_true")
    p.add_argument("--note")
    p.add_argument("--from", dest="source")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--all", action="store_true", help=msg("outdated: include finished documents"))
    p.add_argument("--map", action="append")
    p.add_argument("--to")
    p.add_argument("--dest")
    p = add("legacy", cmd_legacy, msg("Brownfield legacy documents: adopt · todos"))
    p.add_argument("action", choices=["adopt", "todos"])
    p.add_argument("--from", dest="source")
    p = add("hooks", cmd_hooks, msg("Install · remove · show git hooks"))
    p.add_argument("action", choices=["install", "uninstall", "status"])
    add("doctor", cmd_doctor, msg("Check that the layout matches lantern.yaml"))
