"""Folders and documents are born from templates only (P2).

The script copies, numbers and links; the AI only fills the {{blanks}} afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import resources
from ..core import frontmatter, state, templating
from ..core.new_id import next_id
from ..core.profile import CLIENT_LABEL, DATA_VARIANT, OPTIONAL_DOC_KEYS, DocSpec, enabled_docs
from ..core.project import Project, nfc, read, safe_name, today, wikilink, write

BASE_TEMPLATE_DIR = "templates"
WORK_DOCS = {"기획": "기획.md", "설계": "설계.md", "할 일": "할 일.md", "기록": "기록.md"}
WORK_DOC_ALIASES = {"plan": "기획", "design": "설계", "tasks": "할 일", "task": "할 일", "record": "기록", "할일": "할 일"}


# --------------------------------------------------------------------------- templates


def base_template_names() -> list[str]:
    return sorted(nfc(p.stem) for _, p in resources.iter_files(BASE_TEMPLATE_DIR) if p.suffix == ".md")


def base_template_text(name: str) -> str:
    for _, p in resources.iter_files(BASE_TEMPLATE_DIR):
        if p.suffix == ".md" and nfc(p.stem) == nfc(name):
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(f"기본 양식 '{name}'이 없습니다")


def template_version(text: str) -> str:
    return frontmatter.as_str(frontmatter.parse(text).meta.get("template_version")) or "0.0.0"


def project_template_path(project: Project, name: str) -> Path:
    return project.templates_dir / f"{name}.md"


def template_text(project: Project, name: str) -> str:
    """The project's template (`docs/0. 템플릿`) wins; the bundled base is the fallback."""
    p = project_template_path(project, name)
    if p.exists():
        return read(p)
    for cand in project.templates_dir.glob("*.md") if project.templates_dir.exists() else []:
        if nfc(cand.stem) == nfc(name):
            return read(cand)
    return base_template_text(name)


def install_templates(project: Project, names: list[str] | None = None) -> list[str]:
    """Copy base templates into `docs/0. 템플릿` (C-04 option C). Existing files are never overwritten."""
    created: list[str] = []
    st = state.load(project)
    project.templates_dir.mkdir(parents=True, exist_ok=True)
    for name in names or base_template_names():
        dest = project_template_path(project, name)
        if dest.exists():
            continue
        text = base_template_text(name)
        write(dest, text)
        st["templates"][name] = {"based_on": template_version(text), "sha256": state.sha256_text(text)}
        created.append(project.rel(dest))
    enums_dest = project.enums_file
    if not enums_dest.exists():
        text = resources.read_text("templates/_meta/enums.yaml")
        write(enums_dest, text)
        st["templates"]["_meta/enums.yaml"] = {"based_on": "1", "sha256": state.sha256_text(text)}
        created.append(project.rel(enums_dest))
    state.save(project, st)
    return created


# --------------------------------------------------------------------------- context


def condition_context(project: Project) -> dict[str, Any]:
    p = project.profile
    return {
        "clients": p.clients,
        "team": p.team,
        "server": p.server,
        "origin": p.get("project.origin"),
        "ac_format": p.get("plan.ac_format"),
        "design_tool": p.get("design.tool"),
        "knowledge": bool(p.knowledge),
        "ui_reference": p.get("plan.ui_reference"),
    }


def _profile_table(project: Project) -> str:
    p = project.profile
    clients = ", ".join(CLIENT_LABEL.get(c, c) for c in p.clients) or "없음"
    server = {"none": "없음", "external": "외부 서비스", "custom": "직접 구축"}.get(p.server, p.server)
    k = p.knowledge
    rows = [
        ("시작", "🌱 그린필드 (새로)" if not p.brownfield else "🏠 브라운필드 (기존 코드 있음)"),
        ("인원", "1인" if not p.team else f"2인 이상 ({', '.join(p.get('project.members') or [])})"),
        ("화면 유형", clients),
        ("서버", server),
        ("지식 저장소", f"{k['type']} · `{k['path']}`" if k else "없음 (배우는 선로 꺼짐)"),
        (
            "디자인 도구",
            {"claude-design": "Claude Design", "figma": "Figma (MCP)", "canva": "Canva (MCP)"}.get(p.get("design.tool"), "없음"),
        ),
        ("문서 저장", "shared (코드와 함께 올림)" if p.remote == "shared" else "local (docs-local 브랜치, 원격에 안 올림)"),
    ]
    return "| 질문 | 답 |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows)


def _members_table(project: Project) -> str:
    members = project.profile.get("project.members") or []
    if not members:
        return "| 이름 | 역할 |\n|---|---|\n| {{이름}} | {{역할}} |"
    return "| 이름 | 역할 |\n|---|---|\n" + "\n".join(f"| {m} | {{{{역할}}}} |" for m in members)


def base_values(project: Project) -> dict[str, Any]:
    p = project.profile
    members = p.get("project.members") or []
    return {
        **project.enums.context(),  # ${work_status.plan} · ${idea_status.new.label} …
        "today": today(),
        "project": p.get("project.name") or project.root.name,
        "links": "[]",
        "owner": templating.yaml_str(members[0] if (p.team and members) else ""),
        "variant": DATA_VARIANT.get(p.server, p.server),
        "base": p.get("git.base"),
        "profile_table": _profile_table(project),
        "members_table": _members_table(project),
        "legacy_rows": "| {{문서}} | {{무슨 내용}} | {{아직 맞나}} | {{흡수 · 보관 · 옮기기}} | {{새 위치}} |",
    }


def create_from_template(project: Project, template: str, dest: Path, values: dict[str, Any] | None = None) -> Path:
    if dest.exists():
        raise FileExistsError(f"이미 있습니다: {project.rel(dest)}")
    vals = base_values(project)
    vals.update(values or {})
    text = templating.render(template_text(project, template), vals, condition_context(project))
    write(dest, text)
    return dest


# --------------------------------------------------------------------------- init (I-01)


@dataclass
class Action:
    kind: str  # create-folder | create-doc | disable | enable | keep
    spec: DocSpec
    path: Path

    def describe(self, project: Project) -> str:
        label = {
            "create-folder": "📁 새 폴더",
            "create-doc": "📄 새 문서",
            "disable": project.enums.label("current_status", "inactive") + " 표시",
            "enable": project.enums.label("current_status", "active") + "으로 되돌림",
            "keep": "· 그대로",
        }[self.kind]
        return f"{label}  {project.rel(self.path)}  ({self.spec.reason})"


def _doc_status(path: Path) -> str | None:
    if not path.exists() or path.suffix != ".md":
        return None
    return frontmatter.as_str(frontmatter.parse(read(path)).meta.get("status"))


def init_plan(project: Project) -> list[Action]:
    actions: list[Action] = []
    wanted = enabled_docs(project.profile)
    wanted_keys = {s.key for s in wanted}
    for spec in wanted:
        path = project.docs / spec.path
        if spec.path.endswith("/"):
            actions.append(Action("keep" if path.exists() else "create-folder", spec, path))
        elif not path.exists():
            actions.append(Action("create-doc", spec, path))
        elif _doc_status(path) == project.enums.value("current_status", "inactive"):
            actions.append(Action("enable", spec, path))
        else:
            actions.append(Action("keep", spec, path))
    # docs that were enabled before but are not wanted any more → current_status inactive (never delete)
    import copy

    from ..core.profile import Profile
    from ..core.profile import enabled_docs as _ed

    everything = copy.deepcopy(project.profile.data)
    everything["project"]["clients"] = ["web", "desktop", "mobile"]
    everything["project"]["server"] = "custom"
    everything["project"]["team"] = "team"
    everything["docs"]["extra"] = ["api"]
    everything["project"]["origin"] = "brownfield"
    everything["knowledge"] = everything.get("knowledge") or {"type": "obsidian", "path": "x"}
    for spec in _ed(Profile(data=everything)):
        if spec.key in wanted_keys or spec.key not in OPTIONAL_DOC_KEYS:
            continue
        path = project.docs / spec.path
        if path.exists() and _doc_status(path) not in (None, project.enums.value("current_status", "inactive")):
            actions.append(Action("disable", spec, path))
    return actions


def init_apply(project: Project) -> list[str]:
    """Create what is missing, mark what is no longer needed. Existing docs are left alone."""
    done: list[str] = []
    state.ensure_state_dir(project)
    project.docs.mkdir(parents=True, exist_ok=True)
    done += install_templates(project)
    from ..report.obsidian import write_vault  # field choices for opening docs/ in Obsidian (from enums.yaml)

    done += [project.rel(p) for p in write_vault(project)]
    for action in init_plan(project):
        spec, path = action.spec, action.path
        if action.kind == "create-folder":
            path.mkdir(parents=True, exist_ok=True)
            done.append(project.rel(path) + "/")
        elif action.kind == "create-doc":
            path.parent.mkdir(parents=True, exist_ok=True)
            if spec.key == "schema":
                write(path, _schema_stub(project))
            elif spec.key == "debt-status":
                from ..learn.debt import write_status

                write_status(project)
            elif spec.key == "principles":
                from ..report.principles_doc import write_doc

                write_doc(project)
            elif spec.key == "legacy-map" and spec.template:
                from ..check.legacy import legacy_files, map_rows

                create_from_template(project, spec.template, path, {"legacy_rows": map_rows(project, legacy_files(project))})
            elif spec.template:
                create_from_template(project, spec.template, path)
            done.append(project.rel(path))
        elif action.kind == "disable":
            inactive = project.enums.value("current_status", "inactive")
            write(path, frontmatter.set_fields(read(path), {"status": inactive}))
            done.append(project.rel(path) + f" ({inactive})")
        elif action.kind == "enable":
            write(path, frontmatter.set_fields(read(path), {"status": project.enums.value("current_status", "active")}))
            done.append(project.rel(path) + " (다시 사용)")
    if project.profile.clients:
        (project.folder("current") / "화면").mkdir(parents=True, exist_ok=True)
    return done


def _schema_stub(project: Project) -> str:
    variant = DATA_VARIANT.get(project.profile.server, project.profile.server)
    name = project.profile.get("project.name") or project.root.name
    return (
        f"// schema.dbml — {name} 데이터 원본 ({variant}). ERD 그림과 데이터 사전은 `lantern dbml render`가 만든다.\n"
        f"Project \"{name}\" {{\n  Note: '{variant}'\n}}\n"
    )


# --------------------------------------------------------------------------- work · idea · adr


def work_folder_name(work_id: str, name: str) -> str:
    return f"{work_id} {safe_name(name)}"


def new_work(project: Project, name: str, idea_id: str | None = None, ui: bool = False) -> Path:
    work_id = next_id(project, "work")
    folder = project.folder("works") / work_folder_name(work_id, name)
    folder.mkdir(parents=True, exist_ok=False)
    links: list[str] = []
    if idea_id:
        idea = project.find_by_id(idea_id)
        if idea is None:
            raise ValueError(f"아이디어 {idea_id}를 찾지 못했습니다")
        links.append(wikilink(project, idea))
    plan = folder / WORK_DOCS["기획"]
    create_from_template(
        project,
        "기획",
        plan,
        {
            "work_id": work_id,
            "name": safe_name(name),
            "links": templating.yaml_list(links),
        },
    )
    if ui:
        write(plan, frontmatter.set_fields(read(plan), {"ui": True}, touch=False))
    if ui or project.profile.get("design.tool") not in (None, "none"):
        (folder / "화면").mkdir(exist_ok=True)
    return folder


def work_doc(project: Project, work_id: str, kind: str) -> Path:
    kind = WORK_DOC_ALIASES.get(kind, kind)
    if kind not in WORK_DOCS:
        raise ValueError(f"작업 문서 종류는 {', '.join(WORK_DOCS)} 중 하나입니다")
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise ValueError(f"진행 중인 작업 {work_id}를 찾지 못했습니다")
    dest = folder / WORK_DOCS[kind]
    plan = folder / WORK_DOCS["기획"]
    links = [wikilink(project, plan, f"{work_id} 기획")] if plan.exists() and kind != "기획" else []
    from ..core.project import work_name_of

    create_from_template(
        project,
        kind,
        dest,
        {
            "work_id": work_id.upper(),
            "name": work_name_of(folder),
            "links": templating.yaml_list(links),
        },
    )
    return dest


def new_idea(
    project: Project,
    name: str,
    kind: str = "기능",
    raw: str = "",
    status: str | None = None,
    auto: bool = False,
    links: list[str] | None = None,
) -> Path:
    status = status or project.enums.value("idea_status", "new")
    idea_id = next_id(project, "idea")
    dest = project.folder("ideas") / f"{idea_id} {safe_name(name)}.md"
    quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in (raw or name).strip().split("\n"))
    create_from_template(
        project,
        "아이디어",
        dest,
        {
            "id": idea_id,
            "name": safe_name(name),
            "kind": templating.yaml_str(kind),
            "status": templating.yaml_str(status),
            "auto": "true" if auto else "false",
            "raw": f"{today()}\n{quoted}",
            "links": templating.yaml_list(links or []),
        },
    )
    if auto:
        text = read(dest).replace(f"# 💡 {idea_id} {safe_name(name)}", f"# 💡 {idea_id} {safe_name(name)}\n\n> [!info] 🤖 자동 기록", 1)
        write(dest, text)
    return dest


def new_adr(project: Project, name: str, work_id: str | None = None) -> Path:
    adr_id = next_id(project, "adr")
    dest = project.folder("rules") / f"{adr_id} {safe_name(name)}.md"
    links: list[str] = []
    if work_id:
        folder = project.find_work(work_id)
        if folder is None:
            raise ValueError(f"작업 {work_id}를 찾지 못했습니다")
        links.append(wikilink(project, folder / "기획.md", f"{work_id.upper()} 기획"))
    create_from_template(project, "ADR", dest, {"id": adr_id, "name": safe_name(name), "links": templating.yaml_list(links)})
    return dest


def new_meeting(project: Project, name: str) -> Path:
    mid = next_id(project, "meeting")
    dest = project.folder("meetings") / f"{today()} {mid} {safe_name(name)}.md"
    create_from_template(project, "회의록", dest, {"id": mid, "name": safe_name(name)})
    return dest
