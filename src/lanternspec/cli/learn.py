"""배우는 선로 명령: knowledge(지식 연결기) · debt(부채 장부) · mcp."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .common import Add, CliError, _p


def cmd_knowledge(a: argparse.Namespace) -> int:
    from ..learn.knowledge import adapter_for, drafts

    project = _p()
    if a.action == "search":
        hits = adapter_for(project).search(a.arg, aliases=a.alias or [], limit=a.limit)
        if a.json:
            print(json.dumps([h.to_dict() for h in hits], ensure_ascii=False, indent=2))
        elif not hits:
            print(f"🔴 '{a.arg}' 노트 없음")
        else:
            for h in hits:
                print(f"🟢 {h.title}  ({h.path} · {h.updated} · 점수 {h.score})\n   {h.summary}")
        return 0
    if a.action == "read":
        print(adapter_for(project).read(a.arg))
        return 0
    if a.action == "propose":
        content = None
        if a.file:
            content = Path(a.file).read_text(encoding="utf-8")
        elif a.stdin:
            content = sys.stdin.read()
        res = drafts.propose(project, a.arg, content, area=a.area or "", target=a.target or "")
        print(f"✔ 초안 {res['draft']} (승인 대기) → 저장소 위치 제안: {res['target']}")
        if res["write_mode"] == "propose_only":
            print("ℹ propose_only — 승인되면 사용자가 직접 저장소로 옮깁니다")
        return 0
    if a.action == "write":
        draft = Path(a.arg)
        if not draft.is_absolute():
            draft = next((c for c in (project.root / a.arg, project.docs / a.arg) if c.exists()), project.root / a.arg)
        res = drafts.write_draft(project, draft, a.target)
        print(f"✔ 지식 저장소에 씀: {res['path']}")
        return 0
    if a.action == "areas":
        k = project.profile.knowledge or {}
        folder = a.arg or k.get("areas_from")
        if not folder:
            raise CliError('knowledge.areas_from이 없습니다 (lantern knowledge areas "2. Study")')
        from ..core import enums as enums_mod

        have = set(enums_mod.load(project.enums_file).values("area"))
        found = adapter_for(project).areas(str(folder))
        for name in found:
            print(f"{'· 있음' if name.lower() in {h.lower() for h in have} else '✚ 제안'}  {name}")
        return 0
    return 1


def cmd_debt(a: argparse.Namespace) -> int:
    from ..learn import debt

    project = _p()
    if a.action == "find":
        if debt.is_known(project, a.arg):
            print(f"🧠 '{a.arg}'는 아는 기술 — 부채 후보에서 뺀다")
            return 0
        c = debt.find(project, a.arg)
        if c:
            st = str(c.meta.get("status"))
            print(
                f"{debt.status_label(project, st)} {c.id} {c.title} · 물은 횟수 {c.meta.get('ask_count')}"
                f" · 노트 {c.meta.get('note') or '없음'}"
            )
        else:
            print(f"카드 없음: '{a.arg}'")
        return 0
    if a.action == "new":
        p = debt.new_card(
            project,
            a.arg,
            area=a.area or "기타",
            aliases=a.alias or [],
            work=a.work,
            note=a.note,
            session=a.session or "",
            context=a.context or "",
            kind=a.kind,
        )
        print(f"{project.enums.icon('debt_status', 'new')} {project.rel(p)}")
        return 0
    if a.action == "promote":
        print(f"{project.enums.icon('debt_kind', 'competency')} {project.rel(debt.promote(project, a.arg, a.name))}")
        return 0
    if a.action == "practice":
        if not a.name:
            raise CliError('lantern debt practice D-002 "만든 것 · 링크 · 한 줄 소감"')
        print(f"{project.enums.icon('debt_status', 'practicing')} {project.rel(debt.practice(project, a.arg, a.name))}")
        return 0
    if a.action == "ask":
        r = debt.ask(project, a.arg, work=a.work, session=a.session or "", context=a.context or "")
        if not r.counted:
            print(f"· 같은 대화에서 이미 셌습니다 ({r.ask_count}번)")
        else:
            reopened = f" ({project.enums.value('debt_status', 'resolved')} → 다시 열림)" if r.reopened else ""
            print(f"{debt.status_label(project, r.status)} {project.rel(r.card)} — 물은 횟수 {r.ask_count}{reopened}")
        return 0
    if a.action == "resolve":
        print(f"{project.enums.icon('debt_status', 'resolved')} {project.rel(debt.resolve(project, a.arg, a.note))}")
        return 0
    if a.action == "known":
        if a.arg in (None, "list"):
            for names in debt.known_list(project):
                print(" · ".join(names))
            return 0
        if a.arg == "add":
            if not a.name:
                raise CliError('lantern debt known add "기술"')
            print(f"🧠 {project.rel(debt.known_add(project, a.name, a.alias or []))}")
            return 0
        raise CliError("lantern debt known add|list")
    if a.action == "status":
        print(f"✔ {project.rel(debt.write_status(project))}")
        return 0
    if a.action == "list":
        for c in debt.cards(project):
            st = str(c.meta.get("status"))
            print(f"{debt.status_label(project, st)} {c.id} {c.title}  [{c.meta.get('area')}] × {c.meta.get('ask_count')}")
        return 0
    return 1


def cmd_mcp(a: argparse.Namespace) -> int:
    from ..learn.knowledge.mcp_server import serve

    return serve(_p())


def register(add: Add) -> None:
    p = add("knowledge", cmd_knowledge, "지식 연결기: search · read · propose · write · areas")
    p.add_argument("action", choices=["search", "read", "propose", "write", "areas"])
    p.add_argument("arg", nargs="?")
    p.add_argument("--alias", action="append")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--json", action="store_true")
    p.add_argument("--file")
    p.add_argument("--stdin", action="store_true")
    p.add_argument("--area")
    p.add_argument("--target")
    p = add("debt", cmd_debt, "부채 장부: find · new · ask · resolve · promote · practice · known · status · list")
    p.add_argument("action", choices=["find", "new", "ask", "resolve", "promote", "practice", "known", "status", "list"])
    p.add_argument("arg", nargs="?")
    p.add_argument("name", nargs="?")
    p.add_argument("--area")
    p.add_argument("--alias", action="append")
    p.add_argument("--work")
    p.add_argument("--note")
    p.add_argument("--session")
    p.add_argument("--context")
    p.add_argument("--kind", help="new: 이해(기본) | 기술")
    add("mcp", cmd_mcp, "지식 연결기 MCP 서버 (stdio)")
