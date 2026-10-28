"""Document-format commands: profile (lantern.yaml) · principles (design principles) · new-id · meta (frontmatter) · enums (choices)."""

from __future__ import annotations

import argparse
import json

from ..core.messages import msg
from .common import Add, CliError, _csv, _p


def cmd_profile(a: argparse.Namespace) -> int:
    """`lantern profile show|docs|write|set` — show, write or change lantern.yaml, or list the documents it turns on."""
    from ..core import profile as pm
    from ..core.project import read

    project = _p()
    if a.action == "show":
        if not project.profile.exists:
            print(msg("No lantern.yaml — /l-init"))
            return 1
        print(read(project.root / pm.PROFILE_FILE).rstrip())
        return 0
    if a.action == "docs":
        for spec in pm.enabled_docs(project.profile):
            print(f"{spec.path:<45} {spec.reason}")
        return 0
    if a.action == "write":
        data = pm.load(project.root).data if project.profile.exists else dict(pm.DEFAULTS)
        import copy

        data = copy.deepcopy(data)
        proj = data.setdefault("project", {})
        if a.name is not None:
            proj["name"] = a.name
        for key in ("origin", "team", "server", "language", "comment_language"):
            if getattr(a, key) is not None:
                proj[key] = getattr(a, key)
        if a.language is None and not project.profile.exists:  # the language chosen at `lantern install --language`
            from ..core import state

            proj["language"] = state.load(project).get("language") or proj.get("language") or "ko"
        if a.members is not None:
            proj["members"] = _csv(a.members)
        if a.clients is not None:
            proj["clients"] = [] if a.clients in ("none", "없음") else _csv(a.clients)
        if a.kind is not None:
            proj["kind"] = a.kind
        if a.external is not None:
            proj["external"] = a.external in ("yes", "true", "예")
        if a.languages is not None:
            proj["languages"] = [] if a.languages in ("none", "없음") else _csv(a.languages)
        docs = data.setdefault("docs", {})
        if a.remote:
            docs["remote"] = a.remote
        if a.extra is not None:
            docs["extra"] = _csv(a.extra)
        if a.knowledge is not None:
            if a.knowledge in ("", "none", "없음"):
                data["knowledge"] = None
            else:
                k = dict(data.get("knowledge") or {})
                k.update(
                    {
                        "type": a.knowledge_type or k.get("type") or "obsidian",
                        "path": a.knowledge,
                        "write": a.knowledge_write or k.get("write") or "direct",
                    }
                )
                if a.areas_from:
                    k["areas_from"] = a.areas_from
                data["knowledge"] = k
        if a.design:
            data.setdefault("design", {})["tool"] = a.design
        git_cfg = data.setdefault("git", {})
        if a.base:
            git_cfg["base"] = a.base
        if a.hooks:
            git_cfg["hooks"] = a.hooks
        path = pm.save(project.root, data)
        print(msg("✔ Saved {name}", name=path.name))
        print(msg("Next: lantern scaffold init --plan"))
        return 0
    if a.action == "set":
        from ..core.meta import parse_assignments

        path = project.root / pm.PROFILE_FILE
        if not path.exists():
            raise CliError(msg("No lantern.yaml"))
        updates = parse_assignments(a.items)
        if "docs.remote" in updates:
            raise CliError(msg("Document storage changes only with lantern docs-mode local|shared"))
        pm.update(project.root, updates)
        print("✔ " + ", ".join(f"{k}={v}" for k, v in updates.items()))
        if any(k.split(".")[0] in ("idea", "learn", "plan", "design", "build", "report", "docs") for k in updates):
            print(msg("ℹ This value changes how skills work → lantern upgrade"))
        if any(k.startswith("project.") or k == "knowledge" or k == "docs.extra" for k in updates):
            print(msg("ℹ The documents to turn on may change → lantern scaffold init --plan"))
        if any(k in ("project.kind", "project.external", "project.languages", "project.code_size", "project.team") for k in updates):
            print(msg("ℹ The principles change → lantern upgrade (AGENTS.md · the principles document)"))
        return 0
    return 1


def cmd_principles(a: argparse.Namespace) -> int:
    """`lantern principles show|detect` — show the chosen design principles · detect languages and tools already in use."""
    from ..core import principles
    from ..core import profile as pm
    from ..report.harness import code_lines

    project = _p()
    if a.action == "show":
        sel = principles.select(project.profile)
        if sel is None:
            print(msg("lantern.yaml has no project.kind — /l-init (or lantern profile set project.kind=cli)"))
            return 1
        t = principles.table(sel.locale)
        names = t["levels"]
        print(f"■ {sel.summary()}")
        for p in sel.principles:
            print(f"  {names[p.level]:<5} {p.name} — {p.reason}")
        print(msg("  Ways of working: ") + " · ".join(name for name, _ in sel.always))
        for c in sel.conventions:
            print(msg("■ {label} (code {label2})", label=c.label, label2=t["sizes"]["code"][c.size]["label"]))
            for k, v in c.rules.items():
                print(f"  {principles.rule_label(k, sel.locale)}: {v}")
        for role in (*principles.COMMAND_ROLES, "test"):
            cmd = project.profile.get(f"build.{role}")
            print(f"  build.{role}: {cmd or msg('(none)')}")
        return 0
    lines = code_lines(project, tests=False)
    size = principles.code_size(lines)
    d = principles.detect(project.root)
    print(
        msg(
            "{lines:,} lines of code (without tests · docs) → {label} ({size})",
            lines=lines,
            label=principles.table(project.profile.language)["sizes"]["code"][size]["label"],
            size=size,
        )
    )
    if not d.languages:
        print(msg("Languages: none detected — for a new project, ask the user and write them with --languages"))
    for lang in d.languages:
        print(
            msg(
                "Language: {lang} ({value}) · runner '{value2}'",
                lang=lang,
                value=d.evidence[lang],
                value2=d.runners[lang].strip() or msg("none"),
            )
        )
        for role, (name, cmd, ev) in d.existing.get(lang, {}).items():
            print(
                msg(
                    "  {role_label} in use: {name} ({ev}) → `{cmd}`",
                    role_label=principles.role_label(role, project.profile.language),
                    name=name,
                    ev=ev,
                    cmd=cmd,
                )
            )
    if not a.write:
        return 0
    path = project.root / pm.PROFILE_FILE
    if not path.exists():
        raise CliError(msg("No lantern.yaml — run lantern profile write first"))
    data = pm.load(project.root).data
    updates: dict[str, object] = {"project.code_size": size}
    if not data["project"].get("languages") and d.languages:
        updates["project.languages"] = d.languages
    languages = data["project"].get("languages") or d.languages
    d.languages = [x for x in languages if x in principles.language_names()]
    # existing projects record only what is configured (no new tools); values a person wrote are kept
    for role, cmd in d.commands(fill_defaults=not project.profile.brownfield).items():
        if not data["build"].get(role):
            updates[f"build.{role}"] = cmd
    pm.update(project.root, updates)
    print("✔ lantern.yaml: " + ", ".join(f"{k}={v}" for k, v in updates.items()))
    print(msg("Next: lantern principles show → lantern upgrade (into AGENTS.md · the principles document)"))
    return 0


def cmd_new_id(a: argparse.Namespace) -> int:
    """`lantern new-id <kind>` — print the next free ID of a kind."""
    from ..core.new_id import next_id, next_task_id

    project = _p()
    if a.kind == "task":
        if not a.work:
            raise CliError("lantern new-id task W-012")
        print(next_task_id(project, a.work))
    else:
        print(next_id(project, a.kind))
    return 0


def cmd_meta(a: argparse.Namespace) -> int:
    """`lantern meta get|set` — read or change one document's frontmatter."""
    from ..core import frontmatter, meta

    project = _p()
    if a.action == "get":
        val = meta.meta_get(project, a.doc, a.items[0] if a.items else None)
        print(json.dumps(val, ensure_ascii=False, default=str, indent=None if a.items else 2))
        return 0
    path, updates = meta.meta_set(project, a.doc, a.items)
    print(f"✔ {project.rel(path)}: " + ", ".join(f"{k}={frontmatter.as_str(v)}" for k, v in updates.items()))
    return 0


def cmd_enums(a: argparse.Namespace) -> int:
    """`lantern enums list|rename` — show the choice lists, or rename a value everywhere."""
    from ..core import meta, state

    project = _p()
    if a.action == "list":
        for e in project.enums.enums.values():
            if a.name and e.name != a.name:
                continue
            roles = {v: r for r, v in e.roles.items()}
            print(f"{e.name} ({e.label}): " + " · ".join(e.labelled(v) + (f" [{roles[v]}]" if v in roles else "") for v in e.values))
        problems = project.enums.problems()
        for x in problems:
            print(f"✖ {x}")
        return 1 if problems else 0
    if not (a.name and a.old and a.new):
        raise CliError(msg('lantern enums rename <list> <old name> <new name>  (e.g. debt_status "Asked Again" "Asked Twice")'))
    changed = meta.rename_enum_value(project, a.name, a.old, a.new)
    print(f"✔ enums.yaml {a.name}: {a.old} → {a.new}")
    print(
        msg("✔ Also changed the value in {count} documents", count=len(changed))
        + (": " + ", ".join(project.rel(p) for p in changed[:5]) if changed else "")
    )
    if state.load(project).get("version"):  # skills spell names in their text: render them again
        from ..tools.install import install

        rep = install(project)
        print(msg("✔ Regenerated skills ({count})", count=len(rep.written)))
    if project.folder("debt").exists():
        from ..learn.debt import write_status

        write_status(project)
    from ..report.obsidian import write_vault

    write_vault(project)  # Obsidian choices follow the new name too
    return 0


def cmd_sections(a: argparse.Namespace) -> int:
    """`lantern sections list|rename|off|on` — record what the project decided about protected sections."""
    from ..core import profile as pm
    from ..core import state

    project = _p()
    n = project.names
    if a.action == "list":
        for s in n.sections():
            older = [x for x in n.titles(s.role) if x != n.title(s.role)]
            mark = msg(" (not used)") if n.is_unused(s.role) else ""
            print(f"{s.role:<12} ## {n.title(s.role)}{mark}" + (msg("  · old names: {items}", items=", ".join(older)) if older else ""))
            print(f"{'':<12} {s.feature}")
        return 0
    roles = [s.role for s in n.sections()]
    if a.role not in roles:
        raise CliError(msg("A protected-section key is one of {items} (lantern sections list)", items=", ".join(roles)))
    if a.action == "rename":
        if not a.title:
            raise CliError(msg('lantern sections rename {role} "new title"', role=a.role))
        titles = [a.title] + [x for x in n.titles(a.role) if x != a.title and x != n.section(a.role).title]
        if a.title == n.section(a.role).title:
            titles = titles[1:]  # back to the default title: the default is always accepted
        renamed = dict(project.profile.get("docs.sections") or {})
        if titles:
            renamed[a.role] = titles[0] if len(titles) == 1 else titles
        else:
            renamed.pop(a.role, None)
        pm.update(project.root, {"docs.sections": renamed})
        print(
            msg(
                "✔ The '{title}' section is now recognized as '## {title2}' — documents with the old title are still recognized",
                title=n.section(a.role).title,
                title2=a.title,
            )
        )
    else:
        unused = [r for r in project.profile.get("docs.unused_sections") or [] if r != a.role]
        if a.action == "off":
            unused.append(a.role)
        pm.update(project.root, {"docs.unused_sections": unused})
        state_word = msg("turned off — won't ask again") if a.action == "off" else msg("turned back on")
        print(
            msg(
                "✔ The '{title}' section is {state_word} ({feature})",
                title=n.title(a.role),
                state_word=state_word,
                feature=n.section(a.role).feature,
            )
        )
    project = _p()  # read the new decisions
    if state.load(project).get("version"):  # skills spell section titles in their text: render them again
        from ..tools.install import install

        rep = install(project)
        print(msg("✔ Regenerated skills ({count})", count=len(rep.written)))
    else:
        from ..report.sections_doc import write_page

        write_page(project)
    return 0


def register(add: Add) -> None:
    """Register the document-format commands."""
    p = add("profile", cmd_profile, msg("Show · write · edit lantern.yaml · documents to turn on"))
    p.add_argument("action", choices=["show", "docs", "write", "set"])
    p.add_argument("items", nargs="*", help="set: key=value …")
    for flag in (
        "name",
        "origin",
        "team",
        "members",
        "clients",
        "server",
        "language",
        "comment-language",
        "kind",
        "languages",
        "extra",
        "knowledge",
        "knowledge-type",
        "knowledge-write",
        "areas-from",
        "design",
        "remote",
        "base",
        "hooks",
    ):
        p.add_argument(f"--{flag}")
    p.add_argument("--external", choices=["yes", "no"], help=msg("Connects to outside tools · services"))
    p = add("principles", cmd_principles, msg("Design principles · code conventions — show the choice · detect languages and tools in use"))
    p.add_argument("action", choices=["show", "detect"])
    p.add_argument("--write", action="store_true", help=msg("detect: write code size · languages · check commands to lantern.yaml"))
    p = add("new-id", cmd_new_id, msg("Issue the next ID"))
    p.add_argument("kind", choices=["idea", "work", "adr", "debt", "meeting", "task"])
    p.add_argument("work", nargs="?")
    p = add("meta", cmd_meta, msg("Read · write frontmatter"))
    p.add_argument("action", choices=["get", "set"])
    p.add_argument("doc")
    p.add_argument("items", nargs="*")
    p = add("sections", cmd_sections, msg("Protected sections (read and written by lantern): show · report a new title · stop using"))
    p.add_argument("action", choices=["list", "rename", "off", "on"])
    p.add_argument("role", nargs="?", help=msg("Protected-section key (lantern sections list)"))
    p.add_argument("title", nargs="?", help=msg("rename: new title"))
    p = add("enums", cmd_enums, msg("Show status · kind lists · rename values (enums.yaml and document values together)"))
    p.add_argument("action", choices=["list", "rename"])
    p.add_argument("name", nargs="?", help=msg("List name (e.g. debt_status)"))
    p.add_argument("old", nargs="?")
    p.add_argument("new", nargs="?")
