"""Document-format commands: profile (lantern.yaml) · principles (design principles) · new-id · meta (frontmatter) · enums (choices)."""

from __future__ import annotations

import argparse
import json

from .common import Add, CliError, _csv, _p


def cmd_profile(a: argparse.Namespace) -> int:
    """`lantern profile show|docs|write|set` — show, write or change lantern.yaml, or list the documents it turns on."""
    from ..core import profile as pm
    from ..core.project import read

    project = _p()
    if a.action == "show":
        if not project.profile.exists:
            print("lantern.yaml이 없습니다 — /l-init")
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
        print(f"✔ {path.name} 저장")
        print("다음: lantern scaffold init --plan")
        return 0
    if a.action == "set":
        from ..core.meta import parse_assignments

        path = project.root / pm.PROFILE_FILE
        if not path.exists():
            raise CliError("lantern.yaml이 없습니다")
        updates = parse_assignments(a.items)
        if "docs.remote" in updates:
            raise CliError("문서 저장 방식은 lantern docs-mode local|shared 로만 바꿉니다")
        pm.update(project.root, updates)
        print("✔ " + ", ".join(f"{k}={v}" for k, v in updates.items()))
        if any(k.split(".")[0] in ("idea", "learn", "plan", "design", "build", "report", "docs") for k in updates):
            print("ℹ 스킬 동작이 바뀌는 값입니다 → lantern upgrade")
        if any(k.startswith("project.") or k == "knowledge" or k == "docs.extra" for k in updates):
            print("ℹ 켜질 문서가 바뀔 수 있습니다 → lantern scaffold init --plan")
        if any(k in ("project.kind", "project.external", "project.languages", "project.code_size", "project.team") for k in updates):
            print("ℹ 개발 원칙이 바뀝니다 → lantern upgrade (AGENTS.md · 개발 원칙 문서)")
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
            print("lantern.yaml에 project.kind가 없습니다 — /l-init (또는 lantern profile set project.kind=cli)")
            return 1
        names = principles.table()["levels"]
        print(f"■ {sel.summary()}")
        for p in sel.principles:
            print(f"  {names[p.level]:<5} {p.name} — {p.reason}")
        print("  작업 방식: " + " · ".join(name for name, _ in sel.always))
        for c in sel.conventions:
            print(f"■ {c.label} (코드 {principles.table()['sizes']['code'][c.size]['label']})")
            for k, v in c.rules.items():
                print(f"  {principles.RULE_LABEL[k]}: {v}")
        for role in (*principles.COMMAND_ROLES, "test"):
            cmd = project.profile.get(f"build.{role}")
            print(f"  build.{role}: {cmd or '(없음)'}")
        return 0
    lines = code_lines(project, tests=False)
    size = principles.code_size(lines)
    d = principles.detect(project.root)
    print(f"코드 {lines:,}줄 (테스트 · 문서 빼고) → {principles.table()['sizes']['code'][size]['label']} ({size})")
    if not d.languages:
        print("언어: 알아본 것 없음 — 새 프로젝트면 사용자에게 묻고 --languages로 적는다")
    for lang in d.languages:
        print(f"언어: {lang} ({d.evidence[lang]}) · 실행기 '{d.runners[lang].strip() or '없음'}'")
        for role, (name, cmd, ev) in d.existing.get(lang, {}).items():
            print(f"  이미 쓰는 {principles.ROLE_LABEL[role]}: {name} ({ev}) → `{cmd}`")
    if not a.write:
        return 0
    path = project.root / pm.PROFILE_FILE
    if not path.exists():
        raise CliError("lantern.yaml이 없습니다 — lantern profile write 먼저")
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
    print("다음: lantern principles show → lantern upgrade (AGENTS.md · 개발 원칙 문서에 반영)")
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
        raise CliError('lantern enums rename <목록> <옛 이름> <새 이름>  (예: debt_status 되물음 "다시 물음")')
    changed = meta.rename_enum_value(project, a.name, a.old, a.new)
    print(f"✔ enums.yaml {a.name}: {a.old} → {a.new}")
    print(f"✔ 문서 {len(changed)}개의 값도 바꿈" + (": " + ", ".join(project.rel(p) for p in changed[:5]) if changed else ""))
    if state.load(project).get("version"):  # skills spell names in their text: render them again
        from ..tools.install import install

        rep = install(project)
        print(f"✔ 스킬 다시 생성 ({len(rep.written)}개)")
    if project.folder("debt").exists():
        from ..learn.debt import write_status

        write_status(project)
    from ..report.obsidian import write_vault

    write_vault(project)  # Obsidian choices follow the new name too
    return 0


def register(add: Add) -> None:
    """Register the document-format commands."""
    p = add("profile", cmd_profile, "lantern.yaml 보기 · 쓰기 · 고치기 · 켜질 문서")
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
    p.add_argument("--external", choices=["yes", "no"], help="바깥 도구 · 서비스에 붙나")
    p = add("principles", cmd_principles, "개발 원칙 · 코드 컨벤션 — 고른 것 보기 · 언어와 이미 쓰는 도구 알아보기")
    p.add_argument("action", choices=["show", "detect"])
    p.add_argument("--write", action="store_true", help="detect: 코드 규모 · 언어 · 확인 명령을 lantern.yaml에 기록")
    p = add("new-id", cmd_new_id, "다음 ID 발급")
    p.add_argument("kind", choices=["idea", "work", "adr", "debt", "meeting", "task"])
    p.add_argument("work", nargs="?")
    p = add("meta", cmd_meta, "frontmatter 읽기 · 쓰기")
    p.add_argument("action", choices=["get", "set"])
    p.add_argument("doc")
    p.add_argument("items", nargs="*")
    p = add("enums", cmd_enums, "상태 · 유형 목록 보기 · 이름 바꾸기 (enums.yaml과 문서 값을 함께)")
    p.add_argument("action", choices=["list", "rename"])
    p.add_argument("name", nargs="?", help="목록 이름 (예: debt_status)")
    p.add_argument("old", nargs="?")
    p.add_argument("new", nargs="?")
