"""Report and sync commands: report · status · scan · sync · map · eval · harness · obsidian."""

from __future__ import annotations

import argparse
import json

from .common import Add, CliError, _csv, _p, _print


def cmd_report(a: argparse.Namespace) -> int:
    """`lantern report` — write the report views (with up to three summary lines)."""
    from ..report import views as report

    project = _p()
    cur, past = report.run(project, _csv(a.views) or None, a.summary)
    print(f"✔ {project.rel(cur)}\n✔ {project.rel(past)}")
    if not a.summary:
        print('다음: 팀장 보고 3줄 → lantern report --summary "…" "…" "…"')
    return 0


def cmd_status(a: argparse.Namespace) -> int:
    """`lantern status` — print the three-line current status."""
    from ..report.status import lines

    _print(lines(_p()))
    return 0


def cmd_scan(a: argparse.Namespace) -> int:
    """`lantern scan` — find docs-vs-code drift (text or JSON)."""
    from ..report import scan

    res = scan.run(_p(), rev=a.range, limit=a.limit, tests=a.tests)
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
        raise CliError('--work W-012 또는 --none "이유" 중 하나')
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


def cmd_harness(a: argparse.Namespace) -> int:
    """`lantern harness suggest [--apply]` — suggest a work mode for the project size, and apply it when asked."""
    from ..core import profile as pm
    from ..core.project import read, write
    from ..report import harness

    project = _p()
    s = harness.suggest(project)
    f = s.facts
    print(f"추천: {s.mode}")
    for r in s.reasons:
        print(f"  · {r}")
    print(
        f"  (근거: 코드 {f['code_files']}개 파일 · {f['loc']}줄 · 진행 중 작업 {f['active_works']} · 할 일 {f['tasks']}"
        f" · [P] 지금 가능 {f['parallel_ready']} · 테스트 {'있음' if f['has_test'] else '없음'})"
    )
    if s.settings:
        print("  설정: " + ", ".join(f"{k}={v}" for k, v in s.settings.items()))
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
        print("✔ lantern.yaml에 적었습니다 → lantern upgrade (스킬에 반영)")
    return 0


def cmd_obsidian(a: argparse.Namespace) -> int:
    """`lantern obsidian plugins` — download the recommended Obsidian plugins into docs/.obsidian/plugins/."""
    from ..report.obsidian import install_plugins, write_vault

    project = _p()
    write_vault(project)  # plugin settings and .gitignore must exist first
    for plugin_id, version in install_plugins(project):
        print(f"✔ {plugin_id} {version}")
    print("다음: Obsidian에서 docs/ 폴더를 볼트로 열고, 커뮤니티 플러그인을 켜 달라고 물으면 켭니다 (제한 모드 해제)")
    return 0


def register(add: Add) -> None:
    """Register the report and sync commands."""
    p = add("report", cmd_report, "현황 보고 생성")
    p.add_argument("--views")
    p.add_argument("--summary", nargs="+", help="팀장 보고 3줄")
    add("status", cmd_status, "지금 상황 3줄")
    p = add("obsidian", cmd_obsidian, "Obsidian 권장 플러그인(Dataview · Metadata Menu) 받기")
    p.add_argument("action", choices=["plugins"])
    p = add("scan", cmd_scan, "문서-코드 어긋남 찾기")
    p.add_argument("--range", help="git 범위 (예: main..HEAD)")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--tests", action="store_true", help="build.test로 수락 기준 테스트")
    p.add_argument("--json", action="store_true")
    p = add("sync", cmd_sync, "맞추기 결과 기록")
    p.add_argument("action", choices=["adopt"])
    p.add_argument("commit")
    p.add_argument("--work")
    p.add_argument("--none", help="작업 없이 고친 이유")
    add("map", cmd_map, "MOC 갱신")
    p = add("eval", cmd_eval, "AI 작업 평가 — 어떤 구성이 결과에 도움이 됐나 (실행 기록)")
    p.add_argument("--json", action="store_true")
    p = add("harness", cmd_harness, "프로젝트 크기에 맞는 AI 작업 방식 추천 (하네스 · 루프 · 그래프)")
    p.add_argument("action", choices=["suggest"])
    p.add_argument("--apply", action="store_true")
