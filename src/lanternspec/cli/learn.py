"""Learning-line commands: knowledge (knowledge connector) · debt (debt ledger)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..core.messages import msg
from .common import Add, CliError, _p


def cmd_knowledge(a: argparse.Namespace) -> int:
    """`lantern knowledge search|read|propose|write|areas|properties|setup` — talk to the knowledge store, or connect Notion."""
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
        properties = {}
        for pair in a.property or []:
            name, eq, value = pair.partition("=")
            if not eq or not name.strip():
                raise CliError(msg('Write it as --property "name=value": {pair}', pair=pair))
            properties[name.strip()] = value.strip()
        res = drafts.propose(project, a.arg, content, area=a.area or "", target=a.target or "", properties=properties)
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
    if a.action == "properties":
        found = adapter_for(project).properties()
        if a.json:
            print(json.dumps([p.to_dict() for p in found], ensure_ascii=False, indent=2))
        elif not found:
            print(msg("Notes in this store have no properties to fill"))
        for prop in [] if a.json else found:
            print(f"· {prop.name} ({prop.kind})" + (f": {', '.join(prop.options)}" if prop.options else ""))
        return 0
    if a.action == "setup":
        if a.arg != "notion":
            raise CliError(msg("Only Notion has a setup: lantern knowledge setup notion"))
        if not project.profile.exists:
            raise CliError(
                msg(
                    "No lantern.yaml in {root} — run /l-init first and choose Notion there; it tells you when to run this",
                    root=project.root,
                )
            )
        if not sys.stdin.isatty():
            raise CliError(
                msg(
                    "This asks for a token, so run it yourself in a terminal: lantern knowledge setup notion "
                    "(the AI must not see the token, so don't paste it into a chat)"
                )
            )
        from ..learn.knowledge import notion_setup

        return notion_setup.run(project, notion_setup.TerminalIo(), open_browser=not a.no_open)
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


def _asker(a: argparse.Namespace) -> str:
    """Who asked. An AI runs commands without a terminal, so there it has to name the person (a person at a terminal doesn't)."""
    by = (a.by or "").strip(" ,")
    if not by and not sys.stdin.isatty():
        raise CliError(
            msg(
                'Say who asked with --by "<person>" — the ledger keeps what a person asked or chose to keep; '
                "what the AI got stuck on goes to lantern retro note"
            )
        )
    return by


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
        by = _asker(a)
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
            by=by,
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
        r = debt.ask(project, a.arg, work=a.work, session=a.session or "", context=a.context or "", by=_asker(a))
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


def register(add: Add) -> None:
    """Register the learning-line commands."""
    p = add("knowledge", cmd_knowledge, msg("Knowledge connector: search · read · propose · write · areas · properties · setup notion"))
    p.add_argument("action", choices=["search", "read", "propose", "write", "areas", "properties", "setup"])
    p.add_argument("arg", nargs="?")
    p.add_argument("--alias", action="append")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--json", action="store_true")
    p.add_argument("--file")
    p.add_argument("--stdin", action="store_true")
    p.add_argument("--area")
    p.add_argument("--target", help=msg("propose · write: where the note goes (for Notion, its last part is the title)"))
    p.add_argument("--property", action="append", metavar="NAME=VALUE", help=msg("propose: a value for a property of the note"))
    p.add_argument("--no-open", action="store_true", help=msg("setup: don't open Notion's integrations page in the browser"))
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
    p.add_argument("--by", help=msg("new · ask: the person who asked (an AI is refused)"))
    p.add_argument("--kind", help=msg("new: understanding (default) | tech"))
