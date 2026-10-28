"""Learning-line commands: knowledge (knowledge connector) · debt (debt ledger) · mcp."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..core.messages import msg
from .common import Add, CliError, _p


def cmd_knowledge(a: argparse.Namespace) -> int:
    """`lantern knowledge search|read|propose|write|areas` — talk to the knowledge store."""
    from ..learn.knowledge import adapter_for, drafts

    project = _p()
    if a.action == "search":
        hits = adapter_for(project).search(a.arg, aliases=a.alias or [], limit=a.limit)
        if a.json:
            print(json.dumps([h.to_dict() for h in hits], ensure_ascii=False, indent=2))
        elif not hits:
            print(msg("🔴 No note for '{arg}'", arg=a.arg))
        else:
            for h in hits:
                print(
                    msg(
                        "🟢 {title}  ({path} · {updated} · score {score})\n   {summary}",
                        title=h.title,
                        path=h.path,
                        updated=h.updated,
                        score=h.score,
                        summary=h.summary,
                    )
                )
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
        print(msg("✔ Draft {draft} (awaiting approval) → suggested place in the store: {target}", draft=res["draft"], target=res["target"]))
        if res["write_mode"] == "propose_only":
            print(msg("ℹ propose_only — once approved, the user moves it into the store"))
        return 0
    if a.action == "write":
        draft = Path(a.arg)
        if not draft.is_absolute():
            draft = next((c for c in (project.root / a.arg, project.docs / a.arg) if c.exists()), project.root / a.arg)
        res = drafts.write_draft(project, draft, a.target)
        print(msg("✔ Wrote to the knowledge store: {path}", path=res["path"]))
        return 0
    if a.action == "areas":
        k = project.profile.knowledge or {}
        folder = a.arg or k.get("areas_from")
        if not folder:
            raise CliError(msg('No knowledge.areas_from (lantern knowledge areas "2. Study")'))

        have = set(project.enums.values("area"))
        found = adapter_for(project).areas(str(folder))
        for name in found:
            print(f"{msg('· exists') if name.lower() in {h.lower() for h in have} else msg('✚ suggested')}  {name}")
        return 0
    return 1


def cmd_debt(a: argparse.Namespace) -> int:
    """`lantern debt find|new|ask|resolve|promote|practice|known|status|list` — the debt ledger."""
    from ..learn import debt

    project = _p()
    if a.action == "find":
        if debt.is_known(project, a.arg):
            print(msg("🧠 '{arg}' is known tech — left out of debt candidates", arg=a.arg))
            return 0
        c = debt.find(project, a.arg)
        if c:
            st = str(c.meta.get("status"))
            print(
                msg(
                    "{status_label} {id} {title} · asked {get} · note {value}",
                    status_label=debt.status_label(project, st),
                    id=c.id,
                    title=c.title,
                    get=c.meta.get("ask_count"),
                    value=c.meta.get("note") or msg("none"),
                )
            )
        else:
            print(msg("No card: '{arg}'", arg=a.arg))
        return 0
    if a.action == "new":
        p = debt.new_card(
            project,
            a.arg,
            area=a.area,
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
            raise CliError(msg('lantern debt practice D-002 "what you built · link · one-line takeaway"'))
        print(f"{project.enums.icon('debt_status', 'practicing')} {project.rel(debt.practice(project, a.arg, a.name))}")
        return 0
    if a.action == "ask":
        r = debt.ask(project, a.arg, work=a.work, session=a.session or "", context=a.context or "")
        if not r.counted:
            print(msg("· Already counted in this conversation ({ask_count})", ask_count=r.ask_count))
        else:
            reopened = msg(" ({value} → reopened)", value=project.enums.value("debt_status", "resolved")) if r.reopened else ""
            print(
                msg(
                    "{status_label} {rel} — asked {ask_count}{reopened}",
                    status_label=debt.status_label(project, r.status),
                    rel=project.rel(r.card),
                    ask_count=r.ask_count,
                    reopened=reopened,
                )
            )
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
                raise CliError(msg('lantern debt known add "tech"'))
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
    """`lantern mcp` — serve the knowledge contract as an MCP server over stdio."""
    from ..learn.knowledge.mcp_server import serve

    return serve(_p())


def register(add: Add) -> None:
    """Register the learning-line commands."""
    p = add("knowledge", cmd_knowledge, msg("Knowledge connector: search · read · propose · write · areas"))
    p.add_argument("action", choices=["search", "read", "propose", "write", "areas"])
    p.add_argument("arg", nargs="?")
    p.add_argument("--alias", action="append")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--json", action="store_true")
    p.add_argument("--file")
    p.add_argument("--stdin", action="store_true")
    p.add_argument("--area")
    p.add_argument("--target")
    p = add("debt", cmd_debt, msg("Debt ledger: find · new · ask · resolve · promote · practice · known · status · list"))
    p.add_argument("action", choices=["find", "new", "ask", "resolve", "promote", "practice", "known", "status", "list"])
    p.add_argument("arg", nargs="?")
    p.add_argument("name", nargs="?")
    p.add_argument("--area")
    p.add_argument("--alias", action="append")
    p.add_argument("--work")
    p.add_argument("--note")
    p.add_argument("--session")
    p.add_argument("--context")
    p.add_argument("--kind", help=msg("new: understanding (default) | tech"))
    add("mcp", cmd_mcp, msg("Knowledge connector MCP server (stdio)"))
