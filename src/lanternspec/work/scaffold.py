"""Folders and documents are born from templates only.

The script copies, numbers and links; the AI only fills the {{blanks}} afterwards.

Responsibilities:
    - the base templates bundled with the package and the project's copies in `docs/0. 템플릿`
    - the values and conditions every template is filled with
    - `lantern scaffold init`: create the documents the answers turn on, mark the ones no longer needed
    - create works, work documents, ideas, ADRs and meeting notes with the next ID

Not here:
    - filling a template → core/templating.py
    - which documents the answers turn on → core/profile.py (enabled_docs)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import resources
from ..core import frontmatter, state, templating
from ..core.messages import msg
from ..core.names import WORK_DOCS
from ..core.new_id import next_id
from ..core.profile import OPTIONAL_DOC_KEYS, DocSpec, client_label, data_variant, enabled_docs
from ..core.project import Project, nfc, read, safe_name, today, wikilink, write

# --------------------------------------------------------------------------- templates


def _base_dir(language: str) -> str:
    """Folder of a language's base templates inside the resources."""
    return f"locales/{language}/templates"


def base_template_names(language: str = "ko") -> list[str]:
    """List the base templates bundled with the package.

    Args:
        language: Language of the templates (lantern.yaml project.language).

    Returns:
        Template names (file names without `.md`), sorted.

    Example:
        >>> "기획" in base_template_names()
        True
    """
    return sorted(nfc(p.stem) for rel, p in resources.iter_files(_base_dir(language)) if p.suffix == ".md" and "/" not in rel)


def base_template_text(name: str, language: str = "ko") -> str:
    """Read a base template bundled with the package.

    Args:
        name: Template name, e.g. "기획".
        language: Language of the templates.

    Returns:
        The template text.

    Raises:
        FileNotFoundError: No base template has that name.

    Example:
        >>> base_template_text("기획").startswith("---")
        True
    """
    for _, p in resources.iter_files(_base_dir(language)):
        if p.suffix == ".md" and nfc(p.stem) == nfc(name):
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(msg("No base template '{name}'", name=name))


def template_version(text: str) -> str:
    r"""Read the `template_version` of a template.

    Args:
        text: Template text.

    Returns:
        The version; "0.0.0" when the template has none.

    Example:
        >>> template_version("---\ntemplate_version: 1.2.0\n---\n"), template_version("본문")
        ('1.2.0', '0.0.0')
    """
    return frontmatter.as_str(frontmatter.parse(text).meta.get("template_version")) or "0.0.0"


def project_template_path(project: Project, name: str) -> Path:
    """Return where the project's copy of a template lives.

    Args:
        project: The project.
        name: Template name.

    Returns:
        `docs/0. 템플릿/<name>.md` (it may not exist).

    Example:
        >>> project_template_path(project, "기획").name  # doctest: +SKIP
        '기획.md'
    """
    return project.templates_dir / f"{name}.md"


def template_text(project: Project, name: str) -> str:
    """Read a template: the project's copy (`docs/0. 템플릿`) wins; the bundled base is the fallback.

    Args:
        project: The project.
        name: Template name.

    Returns:
        The template text.

    Raises:
        FileNotFoundError: Neither the project nor the package has the template.

    Example:
        >>> template_text(project, "기획").startswith("---")  # doctest: +SKIP
        True
    """
    p = project_template_path(project, name)
    if p.exists():
        return read(p)
    for cand in project.templates_dir.glob("*.md") if project.templates_dir.exists() else []:
        if nfc(cand.stem) == nfc(name):
            return read(cand)
    return base_template_text(name, project.profile.language)


def install_templates(project: Project, names: list[str] | None = None) -> list[str]:
    """Copy base templates and enums.yaml into `docs/0. 템플릿`. Existing files are never overwritten.

    The version and hash of each copy are recorded so upgrades can tell edited copies apart.

    Args:
        project: The project.
        names: Templates to copy; all base templates when None.

    Returns:
        The files created, relative to the project root.

    Example:
        >>> install_templates(project)[:1]  # doctest: +SKIP
        ['docs/0. 템플릿/ADR.md']
    """
    created: list[str] = []
    st = state.load(project)
    project.templates_dir.mkdir(parents=True, exist_ok=True)
    language = project.profile.language
    for name in names or base_template_names(language):
        dest = project_template_path(project, name)
        if dest.exists():
            continue
        text = base_template_text(name, language)
        write(dest, text)
        st["templates"][name] = {"based_on": template_version(text), "sha256": state.sha256_text(text)}
        created.append(project.rel(dest))
    enums_dest = project.enums_file
    if not enums_dest.exists():
        text = resources.read_text(f"{_base_dir(language)}/_meta/enums.yaml")
        write(enums_dest, text)
        st["templates"]["_meta/enums.yaml"] = {"based_on": "1", "sha256": state.sha256_text(text)}
        created.append(project.rel(enums_dest))
    state.save(project, st)
    return created


# --------------------------------------------------------------------------- context


def condition_context(project: Project) -> dict[str, Any]:
    """Collect the values `lantern:if` conditions in templates look at.

    Args:
        project: The project.

    Returns:
        Condition name → value (clients, team, server, origin, ac_format, design_tool, knowledge, ui_reference).

    Example:
        >>> condition_context(project)["team"]  # doctest: +SKIP
        False
    """
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
    clients = ", ".join(client_label(c) for c in p.clients) or msg("none")
    server = {"none": msg("none"), "external": msg("external service"), "custom": msg("built in-house")}.get(p.server, p.server)
    k = p.knowledge
    rows = [
        (msg("Start"), msg("🌱 Greenfield (new)") if not p.brownfield else msg("🏠 Brownfield (existing code)")),
        (msg("Team"), msg("solo") if not p.team else msg("2 or more ({items})", items=", ".join(p.get("project.members") or []))),
        (msg("Clients"), clients),
        (msg("Server"), server),
        (msg("Knowledge store"), f"{k['type']} · `{k['path']}`" if k else msg("none (the learning track is off)")),
        (
            msg("Design tool"),
            {"claude-design": "Claude Design", "figma": "Figma (MCP)", "canva": "Canva (MCP)"}.get(p.get("design.tool"), msg("none")),
        ),
        (msg("Documents"), msg("shared (pushed with the code)") if p.remote == "shared" else msg("local (docs-local branch, not pushed)")),
    ]
    return msg("| Question | Answer |\n|---|---|\n") + "\n".join(f"| {a} | {b} |" for a, b in rows)


def _members_table(project: Project) -> str:
    members = project.profile.get("project.members") or []
    if not members:
        return msg("| Name | Role |\n|---|---|\n| {{{{Name}}}} | {{{{Role}}}} |")
    return msg("| Name | Role |\n|---|---|\n") + "\n".join(msg("| {m} | {{{{Role}}}} |", m=m) for m in members)


def base_values(project: Project) -> dict[str, Any]:
    """Collect the `${…}` values every template can use.

    Args:
        project: The project.

    Returns:
        Value name → value: enum names by role, today, project name, owner, the profile table and more.

    Example:
        >>> base_values(project)["work_status.plan"]  # doctest: +SKIP
        '기획'
    """
    p = project.profile
    members = p.get("project.members") or []
    return {
        **project.enums.context(),  # ${work_status.plan} · ${idea_status.new.label} …
        "today": today(),
        "project": p.get("project.name") or project.root.name,
        "links": "[]",
        "owner": templating.yaml_str(members[0] if (p.team and members) else ""),
        "variant": data_variant(p.server),
        "base": p.get("git.base"),
        "profile_table": _profile_table(project),
        "members_table": _members_table(project),
        "legacy_rows": msg(
            "| {{{{Document}}}} | {{{{What it says}}}} | {{{{Still true?}}}} | {{{{Absorb · Archive · Move}}}} | {{{{New place}}}} |"
        ),
    }


def create_from_template(project: Project, template: str, dest: Path, values: dict[str, Any] | None = None) -> Path:
    """Create one document from a template.

    Args:
        project: The project.
        template: Template name.
        dest: The new document.
        values: Extra `${…}` values (they override the base values).

    Returns:
        The new document.

    Raises:
        FileExistsError: dest already exists.
        FileNotFoundError: The template does not exist.

    Example:
        >>> create_from_template(project, "회의록", project.folder("meetings") / "회의.md").name  # doctest: +SKIP
        '회의.md'
    """
    if dest.exists():
        raise FileExistsError(msg("Already exists: {rel}", rel=project.rel(dest)))
    vals = base_values(project)
    vals.update(values or {})
    text = templating.render(template_text(project, template), vals, condition_context(project))
    write(dest, text)
    return dest


# --------------------------------------------------------------------------- init


@dataclass
class Action:
    """One step of `lantern scaffold init`.

    Attributes:
        kind: "create-folder", "create-doc", "disable", "enable" or "keep".
        spec: The document or folder it is about.
        path: Its path.

    Example:
        >>> [a.kind for a in init_plan(project)][:2]  # doctest: +SKIP
        ['keep', 'create-folder']
    """

    kind: str  # create-folder | create-doc | disable | enable | keep
    spec: DocSpec
    path: Path

    def describe(self, project: Project) -> str:
        """Describe the step in one line for the user.

        Args:
            project: The project (for the status names and relative paths).

        Returns:
            "label  path  (reason)".

        Example:
            >>> init_plan(project)[0].describe(project)  # doctest: +SKIP
            '📄 새 문서  docs/개발문서 MOC.md  (항상)'
        """
        label = {
            "create-folder": msg("📁 new folder"),
            "create-doc": msg("📄 new document"),
            "disable": msg("mark {label}", label=project.enums.label("current_status", "inactive")),
            "enable": msg("back to {label}", label=project.enums.label("current_status", "active")),
            "keep": msg("· unchanged"),
        }[self.kind]
        return f"{label}  {project.rel(self.path)}  ({self.spec.reason})"


def _doc_status(path: Path) -> str | None:
    if not path.exists() or path.suffix != ".md":
        return None
    return frontmatter.as_str(frontmatter.parse(read(path)).meta.get("status"))


def init_plan(project: Project) -> list[Action]:
    """Work out what `lantern scaffold init` would do, without touching anything.

    Documents the answers no longer turn on are marked inactive, never deleted;
    documents marked inactive that are wanted again are turned back on.

    Args:
        project: The project.

    Returns:
        One step per document or folder.

    Example:
        >>> [a.kind for a in init_plan(project) if a.kind != "keep"]  # doctest: +SKIP
        ['create-doc']
    """
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
    """Do `lantern scaffold init`: create what is missing, mark what is no longer needed.

    Existing documents keep their content. Templates, the Obsidian vault settings and
    generated documents (debt status, design principles, legacy map) are written too.

    Args:
        project: The project.

    Returns:
        What was created or changed, relative to the project root.

    Example:
        >>> init_apply(project)[:1]  # doctest: +SKIP
        ['docs/0. 템플릿/ADR.md']
    """
    done: list[str] = []
    state.ensure_state_dir(project)
    project.docs.mkdir(parents=True, exist_ok=True)
    done += install_templates(project)
    from ..report.obsidian import write_vault  # field choices for opening docs/ in Obsidian (from enums.yaml)

    done += [project.rel(p) for p in write_vault(project)]
    from ..report.sections_doc import write_page  # which sections lantern uses, and this project's choices

    page = write_page(project)
    done += [project.rel(page)] if page else []
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
            done.append(project.rel(path) + msg(" (in use again)"))
    if project.profile.clients:
        (project.folder("current") / project.names.folder("screens")).mkdir(parents=True, exist_ok=True)
    return done


def _schema_stub(project: Project) -> str:
    variant = data_variant(project.profile.server)
    name = project.profile.get("project.name") or project.root.name
    return msg(
        "// schema.dbml — {name} data source ({variant}). `lantern dbml render` makes the ERD and "
        "the data dictionary.\nProject \"{name}\" {{\n  Note: '{variant}'\n}}\n",
        name=name,
        variant=variant,
    )


# --------------------------------------------------------------------------- work · idea · adr


def work_folder_name(work_id: str, name: str) -> str:
    """Build the folder name of a work.

    Args:
        work_id: The work ID.
        name: The work's name (made safe for file names).

    Returns:
        "W-012 name".

    Example:
        >>> work_folder_name("W-012", "카카오/로그인")
        'W-012 카카오 로그인'
    """
    return f"{work_id} {safe_name(name)}"


def new_work(project: Project, name: str, idea_id: str | None = None, ui: bool = False) -> Path:
    """Create a new work folder with its plan (`기획.md`), under the next work ID.

    Args:
        project: The project.
        name: The work's name.
        idea_id: The idea it comes from; linked from the plan.
        ui: Mark it as screen work (`ui: true`) and create its mockup folder (`화면/`).

    Returns:
        The new work folder.

    Raises:
        ValueError: idea_id is given but the idea does not exist.

    Example:
        >>> new_work(project, "카카오 로그인", idea_id="IDEA-003").name  # doctest: +SKIP
        'W-013 카카오 로그인'
    """
    work_id = next_id(project, "work")
    folder = project.folder("works") / work_folder_name(work_id, name)
    folder.mkdir(parents=True, exist_ok=False)
    links: list[str] = []
    if idea_id:
        idea = project.find_by_id(idea_id)
        if idea is None:
            raise ValueError(msg("Idea {idea_id} not found", idea_id=idea_id))
        links.append(wikilink(project, idea))
    plan = project.doc_path(folder, "plan")
    create_from_template(
        project,
        project.names.doc("plan"),
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
        (folder / project.names.folder("screens")).mkdir(exist_ok=True)
    return folder


def work_doc_role(project: Project, kind: str) -> str | None:
    """Tell which work document a kind names.

    Args:
        project: The project.
        kind: A role ("plan" · "design" · "tasks" · "record", or "task") or the document's name
            in the project's language (e.g. "설계").

    Returns:
        The role; None when the kind names no work document.

    Example:
        >>> work_doc_role(project, "설계"), work_doc_role(project, "task")  # doctest: +SKIP
        ('design', 'tasks')
    """
    kind = {"task": "tasks"}.get(kind, kind)
    if kind in WORK_DOCS:
        return kind
    return next((r for r in WORK_DOCS if nfc(project.names.doc(r)).casefold() == nfc(kind).casefold()), None)


def work_doc(project: Project, work_id: str, kind: str) -> Path:
    """Create one of a work's documents (기획 · 설계 · 할 일 · 기록), linked to its plan.

    Args:
        project: The project.
        work_id: A work in progress.
        kind: The document's name in the project's language (e.g. "설계") or its role (e.g. "design").

    Returns:
        The new document.

    Raises:
        ValueError: The kind is unknown or the work is not in progress.
        FileExistsError: The document already exists.

    Example:
        >>> work_doc(project, "W-012", "design").name  # doctest: +SKIP
        '설계.md'
    """
    n = project.names
    role = work_doc_role(project, kind)
    if role is None:
        raise ValueError(msg("A work document is one of {items}", items=", ".join(n.doc(r) for r in WORK_DOCS)))
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise ValueError(msg("Work in progress {work_id} not found", work_id=work_id))
    dest = project.doc_path(folder, role)
    plan = project.doc_path(folder, "plan")
    links = [wikilink(project, plan, f"{work_id} {n.doc('plan')}")] if plan.exists() and role != "plan" else []
    from ..core.project import work_name_of

    create_from_template(
        project,
        n.doc(role),
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
    kind: str | None = None,
    raw: str = "",
    status: str | None = None,
    auto: bool = False,
    links: list[str] | None = None,
) -> Path:
    """Create an idea card under the next idea ID, keeping the raw words as a quote.

    Args:
        project: The project.
        name: Short title.
        kind: Idea kind; the first idea_kind value of enums.yaml when None.
        raw: The words as the person said them; the title when empty.
        status: Initial status; the "new" role when None.
        auto: Mark it as recorded automatically (not asked for).
        links: Links to related documents.

    Returns:
        The new idea card.

    Example:
        >>> new_idea(project, "카톡 로그인", raw="카톡으로도 로그인되면 좋겠다").name  # doctest: +SKIP
        'IDEA-004 카톡 로그인.md'
    """
    kind = kind or project.enums.values("idea_kind")[0]
    status = status or project.enums.value("idea_status", "new")
    idea_id = next_id(project, "idea")
    dest = project.folder("ideas") / f"{idea_id} {safe_name(name)}.md"
    quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in (raw or name).strip().split("\n"))
    create_from_template(
        project,
        project.names.doc("idea"),
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
        text = read(dest).replace(
            f"# 💡 {idea_id} {safe_name(name)}",
            msg("# 💡 {idea_id} {safe_name}\n\n> [!info] 🤖 Recorded automatically", idea_id=idea_id, safe_name=safe_name(name)),
            1,
        )
        write(dest, text)
    return dest


def new_adr(project: Project, name: str, work_id: str | None = None) -> Path:
    """Create a decision record (ADR) under the next ADR ID.

    Args:
        project: The project.
        name: The decision's title.
        work_id: The work it was decided in; linked from the record.

    Returns:
        The new record.

    Raises:
        ValueError: work_id is given but the work does not exist.

    Example:
        >>> new_adr(project, "JWT 대신 세션", work_id="W-012").name  # doctest: +SKIP
        'ADR-004 JWT 대신 세션.md'
    """
    adr_id = next_id(project, "adr")
    dest = project.folder("rules") / f"{adr_id} {safe_name(name)}.md"
    links: list[str] = []
    if work_id:
        folder = project.find_work(work_id)
        if folder is None:
            raise ValueError(msg("Work {work_id} not found", work_id=work_id))
        links.append(wikilink(project, project.doc_path(folder, "plan"), f"{work_id.upper()} {project.names.doc('plan')}"))
    create_from_template(
        project, project.names.doc("adr"), dest, {"id": adr_id, "name": safe_name(name), "links": templating.yaml_list(links)}
    )
    return dest


def new_meeting(project: Project, name: str) -> Path:
    """Create meeting notes under the next meeting ID, named with today's date.

    Args:
        project: The project.
        name: The meeting's title.

    Returns:
        The new meeting notes.

    Example:
        >>> new_meeting(project, "주간 회의").name  # doctest: +SKIP
        '2026-10-28 MTG-001 주간 회의.md'
    """
    mid = next_id(project, "meeting")
    dest = project.folder("meetings") / f"{today()} {mid} {safe_name(name)}.md"
    create_from_template(project, project.names.doc("meeting"), dest, {"id": mid, "name": safe_name(name)})
    return dest
