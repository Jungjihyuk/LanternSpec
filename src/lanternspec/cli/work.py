"""Work-line commands: scaffold · idea · design · unit-log · task · work · pack · screen · dbml."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.messages import msg
from ..core.project import Project
from .common import Add, CliError, _csv, _p, _print

if TYPE_CHECKING:
    from ..work import dbml


def cmd_scaffold(a: argparse.Namespace) -> int:
    """`lantern scaffold init|work|doc|idea|adr|meeting|custom` — create folders and documents from templates."""
    from ..core.profile import FOLLOW_UP_QUESTIONS
    from ..work import scaffold

    project = _p()
    if a.kind == "init":
        if not project.profile.exists:
            raise CliError(msg("No lantern.yaml — run lantern profile write first"))
        if a.plan:
            actions = scaffold.init_plan(project)
            todo = [x for x in actions if x.kind != "keep"]
            if not todo:
                print(msg("· Nothing to change (every document exists already)"))
            for x in todo:
                print(x.describe(project))
            asks = [msg(FOLLOW_UP_QUESTIONS[x.spec.key]) for x in todo if x.kind == "create-doc" and x.spec.key in FOLLOW_UP_QUESTIONS]
            if asks and project.docs.exists() and any(project.docs.iterdir()):
                print(msg("To ask: ") + " · ".join(asks))
            return 0
        done = scaffold.init_apply(project)
        from ..report import doc_map

        doc_map.run(project)
        _print([f"✔ {d}" for d in done] or [msg("· Nothing new to make")])
        return 0
    if a.kind == "work":
        folder = scaffold.new_work(project, a.name, idea_id=a.idea, ui=a.ui)
        print(f"✔ {project.rel(project.doc_path(folder, 'plan'))}")
        return 0
    if a.kind == "doc":
        dest = scaffold.work_doc(project, a.work, a.doc)
        print(f"✔ {project.rel(dest)}")
        return 0
    if a.kind == "idea":
        dest = scaffold.new_idea(project, a.name, kind=a.kind_of, raw=a.raw or "", status=a.status, auto=a.auto)
        print(f"✔ {project.rel(dest)}")
        return 0
    if a.kind == "adr":
        print(f"✔ {project.rel(scaffold.new_adr(project, a.name, a.work))}")
        return 0
    if a.kind == "meeting":
        print(f"✔ {project.rel(scaffold.new_meeting(project, a.name))}")
        return 0
    if a.kind == "custom":
        dest = project.docs / a.dest
        scaffold.create_from_template(project, a.template, dest, {"name": dest.stem, "id": f"DOC-{dest.stem}"})
        print(f"✔ {project.rel(dest)}")
        return 0
    return 1


def cmd_idea(a: argparse.Namespace) -> int:
    """`lantern idea find|status` — find overlapping ideas, or move an idea to another status."""
    from ..work import ideas

    project = _p()
    if a.action == "find":
        hits = ideas.idea_find(project, a.arg)
        if not hits:
            print(msg("No overlapping ideas"))
        for h in hits:
            extra = (
                msg(" — dropped because: {dropped_reason}", dropped_reason=h["dropped_reason"])
                if h["status"] == project.enums.value("idea_status", "dropped")
                else ""
            )
            print(
                msg(
                    "{id} {title} ({kind} · {status}) score {score}{extra}",
                    id=h["id"],
                    title=h["title"],
                    kind=h["kind"],
                    status=h["status"],
                    score=h["score"],
                    extra=extra,
                )
            )
        return 0
    if a.action == "status":
        if not a.status:
            raise CliError(msg("lantern idea status IDEA-014 <status>"))
        p = ideas.idea_status(project, a.arg, a.status, work=a.work, reason=a.reason, note=a.note)
        print(f"✔ {project.rel(p)} → {a.status}")
        return 0
    return 1


def cmd_task(a: argparse.Namespace) -> int:
    """`lantern task next|start|done|reopen|list|ac|estimate` — task progress inside /l-build."""
    from ..work import tasks as task_cmd

    project = _p()
    if a.action == "estimate":
        if not a.target:
            raise CliError("lantern task estimate W-012")
        _print(task_cmd.estimate(project, a.target, a.from_date, a.hours, a.apply))
        return 0
    if a.action == "next" and a.all:
        tasks = task_cmd.ready(project, a.target)
        if a.json:
            print(json.dumps([{"id": t.id, "title": t.title, "parallel": t.parallel} for t in tasks], ensure_ascii=False))
            return 0
        if not tasks:
            print(msg("No task can start now"))
        for t in tasks:
            print(f"▶ {t.id}{' [P]' if t.parallel else ''} {t.title} [{project.names.attr('size')}:: {t.size or '?'}]")
        par = [t for t in tasks if t.parallel]
        if len(par) > 1:
            print(msg("ℹ {count} [P] tasks can each go to a parallel agent (one task = one commit)", count=len(par)))
        return 0
    if a.action == "next":
        res = task_cmd.next_task(project, a.target)
        if a.json:
            print(
                json.dumps(
                    {
                        "task": res.task.id if res.task else None,
                        "title": res.task.title if res.task else None,
                        "work": project.rel(res.work) if res.work else None,
                        "all_done": res.all_done,
                        "skipped": [{"id": i, "reason": r} for i, r in res.skipped],
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if res.task:
            t = res.task
            n = project.names
            print(f"▶ {t.id} {t.title} [{n.attr('size')}:: {t.size or '?'}] [{n.attr('criteria')}:: {', '.join(t.criteria) or '—'}]")
        elif res.all_done:
            print(msg("✅ All tasks done — on to updating the current state"))
        else:
            print(msg("No task can start now"))
        for tid, why in res.skipped:
            print(msg("  · skipped {tid}: {why}", tid=tid, why=why))
        return 0
    if a.action == "start":
        t = task_cmd.start(project, a.target)
        print(msg("▶ Started {id} [{attr}:: {started}]", id=t.id, attr=project.names.attr("start"), started=t.started))
        return 0
    if a.action == "done":
        res = task_cmd.done(project, a.target)
        print(msg("✔ Finished {id} [{attr}:: {finished}]", id=res.task.id, attr=project.names.attr("finish"), finished=res.task.finished))
        for ac in res.checkpoints:
            print(
                msg(
                    "🔎 AC checkpoint: {ac} — all linked tasks are done. Check just this criterion, then lantern task ac {work_id} {ac}",
                    ac=ac,
                    work_id=res.task.work_id,
                )
            )
        if res.work_done:
            print(msg("✅ All tasks of this work are done — update the current state"))
        return 0
    if a.action == "reopen":
        t = task_cmd.reopen(project, a.target)
        print(msg("↩ Reopened {id}", id=t.id))
        return 0
    if a.action == "ac":
        if not a.extra:
            raise CliError("lantern task ac W-012 AC-1")
        print(msg("✔ Checked {upper} in {rel}", rel=project.rel(task_cmd.check_ac(project, a.target, a.extra)), upper=a.extra.upper()))
        return 0
    if a.action == "list":
        _print(task_cmd.summary(project, a.target))
        return 0
    return 1


def cmd_task_add(a: argparse.Namespace) -> int:
    """`lantern task add` — append a task line with the next ID."""
    from ..work import tasks as task_cmd

    t = task_cmd.add(
        _p(),
        a.work,
        a.what,
        size=a.size,
        ac=_csv(a.ac),
        after=_csv(a.after),
        owner=a.owner or "",
        screen=a.screen or "",
        start_plan=a.start_plan or "",
        due_plan=a.due_plan or "",
        unknown=a.unknown,
        parallel=a.parallel,
    )
    print(f"✔ {t.raw.strip()}")
    return 0


def cmd_design(a: argparse.Namespace) -> int:
    """`lantern design approve` — record that a work's design was approved."""
    from ..work import stages

    project = _p()
    print(msg("✔ Recorded approval in {rel}", rel=project.rel(stages.design_approve(project, a.work, a.by))))
    return 0


def cmd_unit_log(a: argparse.Namespace) -> int:
    """`lantern unit-log add` — record the work unit the AI recommended and the one the person chose."""
    from ..work import stages

    project = _p()
    print(f"✔ {project.rel(stages.unit_log_add(project, a.what, a.recommended, a.chosen, a.reason))}")
    return 0


def cmd_work(a: argparse.Namespace) -> int:
    """`lantern work branch|start|list|finish|archive|stage` — work branches, parallel worktrees, finishing."""
    from ..work import branches as work
    from ..work import stages

    project = _p()
    if a.action == "branch":
        print(work.ensure_branch(project, a.ids[0]))
    elif a.action == "start":
        _print(work.start(project, a.ids, install=not a.no_install))
    elif a.action == "list":
        _print(work.list_works(project))
    elif a.action == "finish":
        _print(work.finish(project, a.ids[0], test=not a.no_test, keep=a.keep))
    elif a.action == "archive":
        dest = work.archive(project, a.ids[0])
        print(msg("✔ Archived: {rel}", rel=project.rel(dest)))
    elif a.action == "stage":
        if len(a.ids) < 2:
            raise CliError(msg("lantern work stage W-012 <stage>"))
        changed = stages.work_stage(project, a.ids[0], a.ids[1])
        print(msg("✔ {value} → {value2} ({count} documents)", value=a.ids[0], value2=a.ids[1], count=len(changed)))
    return 0


def cmd_pack(a: argparse.Namespace) -> int:
    """`lantern pack W-012` — write the work pack for the AI."""
    from ..work import pack

    project = _p()
    print(f"✔ {project.rel(pack.run(project, a.work, Path(a.out) if a.out else None))}")
    return 0


def cmd_screen(a: argparse.Namespace) -> int:
    """`lantern screen import|compare` — bring mockups in, or compare a capture with its mockup."""
    from ..work import screen

    project = _p()
    if a.action == "import":
        if len(a.args) < 2:
            raise CliError(msg("lantern screen import W-012 <file · folder · zip> …"))
        _print([f"✔ {x}" for x in screen.import_files(project, a.args[0], [Path(x) for x in a.args[1:]])])
        return 0
    if len(a.args) != 2:
        raise CliError(msg("lantern screen compare <build capture.png> <mockup.png>"))
    score, hot = screen.compare(Path(a.args[0]), Path(a.args[1]))
    ok = score >= a.threshold
    print(msg("{value} {score}% like the mockup (threshold {threshold:g}%)", value="✔" if ok else "⚠", score=score, threshold=a.threshold))
    for h in hot:
        print(msg("  · differs: {h}", h=h))
    print(msg('→ The automatic comparison is for reference — show them side by side and ask the person "Does it match the mockup?"'))
    return 0 if ok else 1


def _dbml_source(project: Project, path: str | None) -> tuple[Path, dbml.Schema]:
    """A .dbml file, or the ```dbml blocks of a `설계.md` merged onto the current schema."""
    import re

    from ..core.project import read
    from ..work import dbml

    schema_file = project.folder("current") / project.names.folder("data") / "schema.dbml"
    if not path:
        return schema_file, dbml.parse(read(schema_file)) if schema_file.exists() else dbml.Schema()
    p = Path(path)
    for c in (p, project.root / path, project.docs / path):
        if c.exists():
            p = c
            break
    else:
        raise CliError(msg("Not found: {path}", path=path))
    if p.suffix == ".md":
        blocks = re.findall(r"```dbml\n(.*?)```", read(p), re.S)
        base = read(schema_file) if schema_file.exists() else ""
        delta = dbml.parse("\n".join(blocks))
        merged = dbml.parse(base)
        merged.problems = list(delta.problems)
        merged.tables.update(delta.tables)
        merged.refs += delta.refs
        merged.enums.update(delta.enums)
        return p, merged
    return p, dbml.parse(read(p))


def cmd_dbml(a: argparse.Namespace) -> int:
    """`lantern dbml render|from-sql|diff` — ERD and data dictionary from DBML, DBML from SQL, drift."""
    from ..core.project import read, write
    from ..work import dbml

    project = _p()
    a.sql = (a.sql or []) + (a.sql_opt or [])  # diff takes --sql, from-sql takes positionals
    data_dir = project.folder("current") / project.names.folder("data")
    if a.action == "render":
        schema_file = Path(a.schema) if a.schema else data_dir / "schema.dbml"
        doc = Path(a.doc) if a.doc else data_dir / project.names.file("data")
        if not schema_file.exists():
            raise CliError(msg("No DBML: {rel}", rel=project.rel(schema_file)))
        schema = dbml.parse(read(schema_file))
        errors = [x for x in dbml.check(schema) if x[0] == "error"]
        if errors:
            for _, line, text in errors:
                print(f"✖ {line}: {text}")
            raise CliError(msg("Fix the DBML errors first (lantern check-dbml)"))
        from ..core import frontmatter

        text = read(doc) if doc.exists() else ""
        new = dbml.render_into(text, schema, f"`{project.docs_rel(schema_file)}`")
        new = frontmatter.set_fields(new, {}) if new.startswith("---") else new
        write(doc, new)
        print(msg("✔ ERD · data dictionary → {rel} ({count} tables)", rel=project.rel(doc), count=len(schema.tables)))
        return 0
    files: list[Path] = []
    for raw in a.sql or []:
        p = Path(raw)
        if not p.is_absolute():
            p = project.root / raw
        files += sorted(p.rglob("*.sql")) if p.is_dir() else [p]
    if not files:
        raise CliError(msg("Needs SQL migration files (.sql)"))
    real = dbml.from_sql(files)
    if a.action == "from-sql":
        text = dbml.to_dbml(
            real,
            header=msg(
                "// generated back from {count} migrations — lantern dbml from-sql (migrations are the source of truth)", count=len(files)
            ),
        )
        if a.out:
            out = Path(a.out)
            out = out if out.is_absolute() else project.root / out
            write(out, text)
            print(msg("✔ {rel} ({count} tables)", rel=project.rel(out), count=len(real.tables)))
        else:
            print(text)
        return 0
    # diff
    schema_file = Path(a.schema) if a.schema else data_dir / "schema.dbml"
    doc_schema = dbml.parse(read(schema_file)) if schema_file.exists() else dbml.Schema()
    diffs = dbml.diff(doc_schema, real)
    _print(diffs or [msg("✔ DBML and migrations match")])
    return 1 if diffs else 0


def cmd_check_dbml(a: argparse.Namespace) -> int:
    """`lantern check-dbml` — check DBML syntax and references; exits 1 on errors."""
    from ..work import dbml

    project = _p()
    path, schema = _dbml_source(project, a.path)
    problems = dbml.check(schema)
    icon = {"error": "✖", "warn": "⚠", "info": "ℹ"}
    for level, line, text in problems:
        print(f"{icon[level]} {project.rel(path)}{':' + str(line) if line else ''} {text}")
    errors = [x for x in problems if x[0] == "error"]
    print(
        msg(
            "{value} DBML {count} tables · {count2} relations",
            value="✔" if not errors else "✖",
            count=len(schema.tables),
            count2=len(schema.refs),
        )
        + (msg(" — {count} errors", count=len(errors)) if errors else "")
    )
    return 1 if errors else 0


def register(add: Add) -> None:
    """Register the work-line commands."""
    p = add("scaffold", cmd_scaffold, msg("Make folders · documents from templates"))
    ss = p.add_subparsers(dest="kind", required=True)
    s = ss.add_parser("init", help=msg("Folders · templates · MOC as lantern.yaml says"))
    s.add_argument("--plan", action="store_true", help=msg("Only show what would be made"))
    s = ss.add_parser("work", help=msg("Work folder + plan document"))
    s.add_argument("name")
    s.add_argument("--idea")
    s.add_argument("--ui", action="store_true", help=msg("A work that changes screens"))
    s = ss.add_parser("doc", help=msg("Work document (design · tasks · log)"))
    s.add_argument("work")
    s.add_argument("doc")
    s = ss.add_parser("idea", help=msg("Idea card"))
    s.add_argument("name")
    s.add_argument("--kind", dest="kind_of", help=msg("Idea kind (default: the first value of enums.yaml idea_kind)"))
    s.add_argument("--raw")
    s.add_argument("--status", help=msg("Default: new in enums.yaml idea_status"))
    s.add_argument("--auto", action="store_true", help=msg("Mark as 🤖 recorded automatically"))
    s = ss.add_parser("adr", help=msg("Decision record"))
    s.add_argument("name")
    s.add_argument("--work")
    s = ss.add_parser("meeting", help=msg("Meeting notes (2 or more people)"))
    s.add_argument("name")
    s = ss.add_parser("custom", help=msg("A document from a custom template"))
    s.add_argument("template")
    s.add_argument("dest", help=msg("path in docs.md"))
    p = add("idea", cmd_idea, msg("Ideas: find (overlaps) · status"))
    p.add_argument("action", choices=["find", "status"])
    p.add_argument("arg")
    p.add_argument("status", nargs="?")
    p.add_argument("--work")
    p.add_argument("--reason")
    p.add_argument("--note")
    p = add("design", cmd_design, msg("Record design approval"))
    p.add_argument("action", choices=["approve"])
    p.add_argument("work")
    p.add_argument("--by", required=True)
    p = add("unit-log", cmd_unit_log, msg("Record why the person changed the suggested work unit"))
    p.add_argument("action", choices=["add"])
    p.add_argument("--what", required=True)
    p.add_argument("--recommended", required=True)
    p.add_argument("--chosen", required=True)
    p.add_argument("--reason", required=True)
    p = add("task", cmd_task, msg("Tasks: next · start · done (inside /l-build)"))
    p.add_argument("action", choices=["next", "start", "done", "reopen", "list", "ac", "estimate"])
    p.add_argument("target", nargs="?")
    p.add_argument("extra", nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true", help=msg("next: every task that can start now ([P] ones go to parallel agents)"))
    p.add_argument("--from", dest="from_date", help=msg("estimate: start date"))
    p.add_argument("--hours", type=float, default=6.0, help=msg("estimate: working hours a day"))
    p.add_argument("--apply", action="store_true", help=msg("estimate: write the suggestion into the tasks document"))
    p = add("task-add", cmd_task_add, argparse.SUPPRESS)
    p.add_argument("work")
    p.add_argument("what")
    for flag, default in (
        ("size", "M"),
        ("ac", None),
        ("after", None),
        ("owner", None),
        ("screen", None),
        ("start-plan", None),
        ("due-plan", None),
    ):
        p.add_argument(f"--{flag}", default=default)
    p.add_argument("--unknown", action="store_true")
    p.add_argument("--parallel", action="store_true", help=msg("[P] can run at the same time as other [P] tasks"))
    p = add("work", cmd_work, msg("Work branches · parallel works · finish · archive · stage"))
    p.add_argument("action", choices=["branch", "start", "list", "finish", "archive", "stage"])
    p.add_argument("ids", nargs="*")
    p.add_argument("--no-install", action="store_true")
    p.add_argument("--no-test", action="store_true")
    p.add_argument("--keep", action="store_true")
    p = add("pack", cmd_pack, msg("Work pack (a one-off summary for the AI)"))
    p.add_argument("work")
    p.add_argument("--out")
    p = add("screen", cmd_screen, msg("Screen mockups: import (files · bundles → screens folder) · compare (capture ↔ mockup)"))
    p.add_argument("action", choices=["import", "compare"])
    p.add_argument("args", nargs="*")
    p.add_argument("--threshold", type=float, default=90.0)
    p = add("dbml", cmd_dbml, msg("DBML → ERD · data dictionary, SQL → DBML, drift"))
    p.add_argument("action", choices=["render", "from-sql", "diff"])
    p.add_argument("sql", nargs="*", help=msg("from-sql: migration files · folders"))
    p.add_argument("--sql", dest="sql_opt", action="append", help=msg("diff: migration files · folders"))
    p.add_argument("--schema")
    p.add_argument("--doc")
    p.add_argument("--out")
    p = add("check-dbml", cmd_check_dbml, msg("Check DBML (.dbml or the dbml block in a design document)"))
    p.add_argument("path", nargs="?")
