"""Work-line commands: scaffold · idea · design · unit-log · task · work · pack · screen · dbml."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

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
            raise CliError("lantern.yaml이 없습니다 — lantern profile write 먼저")
        if a.plan:
            actions = scaffold.init_plan(project)
            todo = [x for x in actions if x.kind != "keep"]
            if not todo:
                print("· 바뀔 것이 없습니다 (모든 문서가 이미 있음)")
            for x in todo:
                print(x.describe(project))
            asks = [FOLLOW_UP_QUESTIONS[x.spec.key] for x in todo if x.kind == "create-doc" and x.spec.key in FOLLOW_UP_QUESTIONS]
            if asks and project.docs.exists() and any(project.docs.iterdir()):
                print("물을 것: " + " · ".join(asks))
            return 0
        done = scaffold.init_apply(project)
        from ..report import doc_map

        doc_map.run(project)
        _print([f"✔ {d}" for d in done] or ["· 새로 만들 것이 없습니다"])
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
            print("겹치는 아이디어 없음")
        for h in hits:
            extra = f" — 버린 이유: {h['dropped_reason']}" if h["status"] == project.enums.value("idea_status", "dropped") else ""
            print(f"{h['id']} {h['title']} ({h['kind']} · {h['status']}) 점수 {h['score']}{extra}")
        return 0
    if a.action == "status":
        if not a.status:
            raise CliError("lantern idea status IDEA-014 <상태>")
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
            print("지금 시작할 수 있는 할 일이 없습니다")
        for t in tasks:
            print(f"▶ {t.id}{' [P]' if t.parallel else ''} {t.title} [{project.names.attr('size')}:: {t.size or '?'}]")
        par = [t for t in tasks if t.parallel]
        if len(par) > 1:
            print(f"ℹ [P] {len(par)}개는 병렬 에이전트에 하나씩 맡길 수 있습니다 (할 일 하나 = 커밋 하나)")
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
            print("✅ 모든 할 일 완료 — 현재 상태 반영 단계로")
        else:
            print("지금 시작할 수 있는 할 일이 없습니다")
        for tid, why in res.skipped:
            print(f"  · 건너뜀 {tid}: {why}")
        return 0
    if a.action == "start":
        t = task_cmd.start(project, a.target)
        print(f"▶ {t.id} 시작 [{project.names.attr('start')}:: {t.started}]")
        return 0
    if a.action == "done":
        res = task_cmd.done(project, a.target)
        print(f"✔ {res.task.id} 완료 [{project.names.attr('finish')}:: {res.task.finished}]")
        for ac in res.checkpoints:
            print(f"🔎 AC 체크포인트: {ac} — 연결된 할 일이 모두 끝났습니다. 이 기준만 확인하고 lantern task ac {res.task.work_id} {ac}")
        if res.work_done:
            print("✅ 이 작업의 할 일을 모두 끝냈습니다 — 현재 상태 반영")
        return 0
    if a.action == "reopen":
        t = task_cmd.reopen(project, a.target)
        print(f"↩ {t.id} 다시 열림")
        return 0
    if a.action == "ac":
        if not a.extra:
            raise CliError("lantern task ac W-012 AC-1")
        print(f"✔ {project.rel(task_cmd.check_ac(project, a.target, a.extra))} {a.extra.upper()} 체크")
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
    print(f"✔ {project.rel(stages.design_approve(project, a.work, a.by))} 승인 기록")
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
        print(f"✔ 보관: {project.rel(dest)}")
    elif a.action == "stage":
        if len(a.ids) < 2:
            raise CliError("lantern work stage W-012 <단계>")
        changed = stages.work_stage(project, a.ids[0], a.ids[1])
        print(f"✔ {a.ids[0]} → {a.ids[1]} ({len(changed)}개 문서)")
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
            raise CliError("lantern screen import W-012 <파일 · 폴더 · zip> …")
        _print([f"✔ {x}" for x in screen.import_files(project, a.args[0], [Path(x) for x in a.args[1:]])])
        return 0
    if len(a.args) != 2:
        raise CliError("lantern screen compare <구현 캡처.png> <시안.png>")
    score, hot = screen.compare(Path(a.args[0]), Path(a.args[1]))
    ok = score >= a.threshold
    print(f"{'✔' if ok else '⚠'} 시안과 {score}% 비슷함 (기준 {a.threshold:g}%)")
    for h in hot:
        print(f"  · 다른 곳: {h}")
    print('→ 자동 비교는 참고용 — 나란히 보여 주고 사람에게 "시안과 같나요?"를 묻는다')
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
        raise CliError(f"없습니다: {path}")
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
            raise CliError(f"DBML이 없습니다: {project.rel(schema_file)}")
        schema = dbml.parse(read(schema_file))
        errors = [x for x in dbml.check(schema) if x[0] == "error"]
        if errors:
            for _, line, msg in errors:
                print(f"✖ {line}: {msg}")
            raise CliError("DBML 오류를 먼저 고치세요 (lantern check-dbml)")
        from ..core import frontmatter

        text = read(doc) if doc.exists() else ""
        new = dbml.render_into(text, schema, f"`{project.docs_rel(schema_file)}`")
        new = frontmatter.set_fields(new, {}) if new.startswith("---") else new
        write(doc, new)
        print(f"✔ ERD · 데이터 사전 → {project.rel(doc)} (테이블 {len(schema.tables)}개)")
        return 0
    files: list[Path] = []
    for raw in a.sql or []:
        p = Path(raw)
        if not p.is_absolute():
            p = project.root / raw
        files += sorted(p.rglob("*.sql")) if p.is_dir() else [p]
    if not files:
        raise CliError("SQL 마이그레이션 파일(.sql)이 필요합니다")
    real = dbml.from_sql(files)
    if a.action == "from-sql":
        text = dbml.to_dbml(real, header=f"// 마이그레이션 {len(files)}개에서 역생성 — lantern dbml from-sql (마이그레이션이 기준)")
        if a.out:
            out = Path(a.out)
            out = out if out.is_absolute() else project.root / out
            write(out, text)
            print(f"✔ {project.rel(out)} (테이블 {len(real.tables)}개)")
        else:
            print(text)
        return 0
    # diff
    schema_file = Path(a.schema) if a.schema else data_dir / "schema.dbml"
    doc_schema = dbml.parse(read(schema_file)) if schema_file.exists() else dbml.Schema()
    diffs = dbml.diff(doc_schema, real)
    _print(diffs or ["✔ DBML과 마이그레이션이 같습니다"])
    return 1 if diffs else 0


def cmd_check_dbml(a: argparse.Namespace) -> int:
    """`lantern check-dbml` — check DBML syntax and references; exits 1 on errors."""
    from ..work import dbml

    project = _p()
    path, schema = _dbml_source(project, a.path)
    problems = dbml.check(schema)
    icon = {"error": "✖", "warn": "⚠", "info": "ℹ"}
    for level, line, msg in problems:
        print(f"{icon[level]} {project.rel(path)}{':' + str(line) if line else ''} {msg}")
    errors = [x for x in problems if x[0] == "error"]
    print(
        f"{'✔' if not errors else '✖'} DBML 테이블 {len(schema.tables)}개 · 관계 {len(schema.refs)}개"
        + (f" — 오류 {len(errors)}개" if errors else "")
    )
    return 1 if errors else 0


def register(add: Add) -> None:
    """Register the work-line commands."""
    p = add("scaffold", cmd_scaffold, "템플릿으로 폴더 · 문서 만들기")
    ss = p.add_subparsers(dest="kind", required=True)
    s = ss.add_parser("init", help="lantern.yaml대로 폴더 · 템플릿 · MOC")
    s.add_argument("--plan", action="store_true", help="만들 것만 보여 주기")
    s = ss.add_parser("work", help="작업 폴더 + 기획 문서")
    s.add_argument("name")
    s.add_argument("--idea")
    s.add_argument("--ui", action="store_true", help="화면이 바뀌는 작업")
    s = ss.add_parser("doc", help="작업 문서 (설계 · 할 일 · 기록)")
    s.add_argument("work")
    s.add_argument("doc")
    s = ss.add_parser("idea", help="아이디어 카드")
    s.add_argument("name")
    s.add_argument("--kind", dest="kind_of", help="아이디어 유형 (기본: enums.yaml idea_kind의 첫 값)")
    s.add_argument("--raw")
    s.add_argument("--status", help="기본: enums.yaml idea_status의 new")
    s.add_argument("--auto", action="store_true", help="🤖 자동 기록 표시")
    s = ss.add_parser("adr", help="결정 기록")
    s.add_argument("name")
    s.add_argument("--work")
    s = ss.add_parser("meeting", help="회의록 (2인 이상)")
    s.add_argument("name")
    s = ss.add_parser("custom", help="직접 만든 양식으로 문서")
    s.add_argument("template")
    s.add_argument("dest", help="docs 안 경로.md")
    p = add("idea", cmd_idea, "아이디어: find(겹침) · status")
    p.add_argument("action", choices=["find", "status"])
    p.add_argument("arg")
    p.add_argument("status", nargs="?")
    p.add_argument("--work")
    p.add_argument("--reason")
    p.add_argument("--note")
    p = add("design", cmd_design, "설계 승인 기록")
    p.add_argument("action", choices=["approve"])
    p.add_argument("work")
    p.add_argument("--by", required=True)
    p = add("unit-log", cmd_unit_log, "작업 단위 추천을 사람이 바꾼 이유 기록")
    p.add_argument("action", choices=["add"])
    p.add_argument("--what", required=True)
    p.add_argument("--recommended", required=True)
    p.add_argument("--chosen", required=True)
    p.add_argument("--reason", required=True)
    p = add("task", cmd_task, "할 일 다음 · 시작 · 완료 (/l-build 안에서)")
    p.add_argument("action", choices=["next", "start", "done", "reopen", "list", "ac", "estimate"])
    p.add_argument("target", nargs="?")
    p.add_argument("extra", nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true", help="next: 지금 시작할 수 있는 할 일 전부 ([P]는 병렬 에이전트로)")
    p.add_argument("--from", dest="from_date", help="estimate: 시작 날짜")
    p.add_argument("--hours", type=float, default=6.0, help="estimate: 하루 작업 시간")
    p.add_argument("--apply", action="store_true", help="estimate: 제안을 할 일 문서에 적기")
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
    p.add_argument("--parallel", action="store_true", help="[P] 다른 [P] 할 일과 동시에 할 수 있음")
    p = add("work", cmd_work, "작업 브랜치 · 동시 작업 · 마치기 · 보관 · 단계")
    p.add_argument("action", choices=["branch", "start", "list", "finish", "archive", "stage"])
    p.add_argument("ids", nargs="*")
    p.add_argument("--no-install", action="store_true")
    p.add_argument("--no-test", action="store_true")
    p.add_argument("--keep", action="store_true")
    p = add("pack", cmd_pack, "작업 꾸러미 (AI용 한 번 쓰는 요약)")
    p.add_argument("work")
    p.add_argument("--out")
    p = add("screen", cmd_screen, "화면 시안: import(파일 · 묶음 → 화면/) · compare(캡처 ↔ 시안)")
    p.add_argument("action", choices=["import", "compare"])
    p.add_argument("args", nargs="*")
    p.add_argument("--threshold", type=float, default=90.0)
    p = add("dbml", cmd_dbml, "DBML → ERD · 데이터 사전, SQL → DBML, 어긋남")
    p.add_argument("action", choices=["render", "from-sql", "diff"])
    p.add_argument("sql", nargs="*", help="from-sql: 마이그레이션 파일 · 폴더")
    p.add_argument("--sql", dest="sql_opt", action="append", help="diff: 마이그레이션 파일 · 폴더")
    p.add_argument("--schema")
    p.add_argument("--doc")
    p.add_argument("--out")
    p = add("check-dbml", cmd_check_dbml, "DBML 검사 (.dbml 또는 설계 문서의 dbml 블록)")
    p.add_argument("path", nargs="?")
