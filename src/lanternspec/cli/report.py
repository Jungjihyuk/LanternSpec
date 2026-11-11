"""Report and sync commands: report · status · scan · sync · map · eval · build-mode · obsidian."""

from __future__ import annotations

import argparse
import json
import unicodedata

from ..core.messages import msg
from .common import Add, CliError, _csv, _p, _print


def cmd_report(a: argparse.Namespace) -> int:
    """`lantern report` — write the report views (with up to three summary lines)."""
    from ..report import views as report

    project = _p()
    cur, past = report.run(project, _csv(a.views) or None, a.summary)
    print(f"✔ {project.rel(cur)}\n✔ {project.rel(past)}")
    if not a.summary:
        print(msg('Next: 3-line summary → lantern report --summary "…" "…" "…"'))
    return 0


def cmd_resume(a: argparse.Namespace) -> int:
    """`lantern resume` — sum up an earlier conversation so any AI tool can carry it on."""
    from ..report.resume import summary

    _print(summary(_p(), a.session, a.more))
    return 0


def cmd_status(a: argparse.Namespace) -> int:
    """`lantern status` — print the three-line current status."""
    from ..report.status import lines

    _print(lines(_p()))
    return 0


def cmd_scan(a: argparse.Namespace) -> int:
    """`lantern scan` — find docs-vs-code drift (text or JSON)."""
    from ..report import scan

    res = scan.run(_p(), rev=a.range, limit=a.limit, tests=a.tests, ci=a.ci)
    print(res.to_json() if a.json else res.format())
    return 1 if res.tests is not None and not res.tests.get("ok") else 0  # CI fails on broken acceptance tests


def cmd_sync(a: argparse.Namespace) -> int:
    """`lantern sync adopt` — record what /l-sync decided about an unowned change."""
    from ..report import scan

    project = _p()
    if a.work:
        print(f"✔ {project.rel(scan.adopt_into_work(project, a.commit, a.work))}")
    elif a.none:
        print(f"✔ {project.rel(scan.record_no_work(project, a.commit, a.none))}")
    else:
        raise CliError(msg('One of --work W-012 or --none "reason"'))
    return 0


def cmd_map(a: argparse.Namespace) -> int:
    """`lantern map` — rewrite the MOC's generated block."""
    project = _p()
    from ..report import doc_map

    print(f"✔ {project.rel(doc_map.run(project))}")
    return 0


def cmd_eval(a: argparse.Namespace) -> int:
    """`lantern eval` — show the AI work evaluation (text or JSON)."""
    from ..report import evaluate

    project = _p()
    if a.json:
        print(json.dumps(evaluate.summary(project), ensure_ascii=False, indent=2))
    else:
        print(evaluate.markdown(project))
    return 0


def cmd_build_mode(a: argparse.Namespace) -> int:
    """`lantern build-mode suggest [--apply]` — suggest how to build, one axis at a time, and apply the loop scope when asked."""
    from ..core import profile as pm
    from ..core.project import read, write
    from ..report import build_mode

    project = _p()
    if a.command == "harness":
        print(msg("ℹ `lantern harness` is now `lantern build-mode` — the old name goes away in a later version"))
    s = build_mode.suggest(project)
    f = s.facts

    def cells(text: str) -> int:  # Korean and other wide letters take two columns in a terminal
        return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)

    width = max(cells(ax.name) for ax in s.axes)
    for ax in s.axes:
        print(f"{ax.name}{' ' * (width - cells(ax.name))}  {ax.choice}")
        for r in ax.reasons:
            print(f"{' ' * width}    · {r}")
    print(
        msg(
            "  (based on: {code_files} code files · {loc} lines · works in progress {active_works} · "
            "tasks {tasks} · [P] ready now {parallel_ready} · tests {value})",
            code_files=f["code_files"],
            loc=f["loc"],
            active_works=f["active_works"],
            tasks=f["tasks"],
            parallel_ready=f["parallel_ready"],
            value=msg("yes") if f["has_test"] else msg("no"),
        )
    )
    print(msg("  --apply sets only the loop scope: ") + ", ".join(f"{k}={v}" for k, v in s.settings.items()))
    if a.apply and s.settings:
        path = project.root / pm.PROFILE_FILE
        text = read(path)
        for k, v in s.settings.items():
            new = pm.set_in_text(text, k, v)
            if new is None:
                data = pm.load(project.root).data
                for kk, vv in s.settings.items():
                    pm.set_path(data, kk, vv)
                pm.save(project.root, data)
                text = read(path)
                break
            text = new
        write(path, text)
        print(msg("✔ Written to lantern.yaml → lantern upgrade (into the skills)"))
    return 0


def cmd_obsidian(a: argparse.Namespace) -> int:
    """`lantern obsidian plugins` — download the recommended Obsidian plugins into docs/.obsidian/plugins/."""
    from ..report.obsidian import BUNDLED_PLUGINS, install_plugins, write_vault

    project = _p()
    write_vault(project)  # plugin settings and .gitignore must exist first
    for plugin_id, version in install_plugins(project):
        print(f"✔ {plugin_id} {version}")
    write_vault(project)  # now that plugins are in use, this also copies the plugins bundled with the package
    for plugin in BUNDLED_PLUGINS:
        print(f"✔ {plugin}")
    print(msg("Next: open the docs/ folder as a vault in Obsidian, and turn community plugins on when asked (turn off restricted mode)"))
    return 0


def register(add: Add) -> None:
    """Register the report and sync commands."""
    p = add("report", cmd_report, msg("Make the status report"))
    p.add_argument("--views")
    p.add_argument("--summary", nargs="+", help=msg("3-line summary"))
    add("status", cmd_status, msg("Where things stand in 3 lines"))
    p = add("resume", cmd_resume, msg("Carry on an earlier conversation in any AI tool — where it stopped, even if it was cut off"))
    p.add_argument("--session", help=msg("Which conversation: its number in the list or the start of its id"))
    p.add_argument("--more", type=int, default=0, help=msg("Show this many pages further back"))
    p = add("obsidian", cmd_obsidian, msg("Download the recommended Obsidian plugins (Dataview · Metadata Menu)"))
    p.add_argument("action", choices=["plugins"])
    p = add("scan", cmd_scan, msg("Find doc-code mismatches"))
    p.add_argument("--range", help=msg("git range (e.g. main..HEAD)"))
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--tests", action="store_true", help=msg("Run acceptance tests (each part's test command, or build.test)"))
    p.add_argument("--ci", action="store_true", help=msg("For CI: leave out parts with ci: false"))
    p.add_argument("--json", action="store_true")
    p = add("sync", cmd_sync, msg("Record the result of aligning"))
    p.add_argument("action", choices=["adopt"])
    p.add_argument("commit")
    p.add_argument("--work")
    p.add_argument("--none", help=msg("Why it was changed without a work"))
    add("map", cmd_map, msg("Update the MOC"))
    p = add("eval", cmd_eval, msg("Evaluate AI work — which setups helped (run records)"))
    p.add_argument("--json", action="store_true")
    for name in ("build-mode", "harness"):  # harness: the old name, kept for a while
        p = add(name, cmd_build_mode, msg("Suggest how to build: loop scope · task delegation · parallel works"))
        p.add_argument("action", choices=["suggest"])
        p.add_argument("--apply", action="store_true")
